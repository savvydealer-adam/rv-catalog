"""Sync rv-catalog SQLite -> STL RV Supabase.

One-way: rv-catalog is the source of truth for OEM data, STL RV's KB tables
are the sink. STL RV's admin UI keeps using its existing /api/knowledge/*
endpoints unchanged — those just see fresher / richer data after a sync run.

Natural keys (so re-runs are idempotent):
- manufacturers: name
- models:        (manufacturer_id, model_name, model_year)
- floorplans:    (model_id, floorplan_code)
- kb_images:     (model_id, source_url)

Never deletes. New brand from rv-catalog -> insert. Existing row with changed
fields -> PATCH the diff. Identical row -> skip.

Env:
  SUPABASE_URL           default: https://blcoiejnzrdxjwgxmlui.supabase.co
  SUPABASE_SERVICE_KEY   required (PostgREST service-role JWT)

Usage:
  python scripts/sync_to_stl_rv.py --dry-run             # diff, no writes
  python scripts/sync_to_stl_rv.py --slug jayco          # one brand only
  python scripts/sync_to_stl_rv.py                       # full sync
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_SUPABASE_URL = "https://blcoiejnzrdxjwgxmlui.supabase.co"
DB_PATH = Path(__file__).resolve().parents[1] / "data" / "rv_catalog.db"

INSERT_BATCH = 100
PAGE = 1000


# ---------------------------------------------------------------------------
# Supabase REST client
# ---------------------------------------------------------------------------


class Supa:
    def __init__(self, url: str, key: str):
        self.url = url.rstrip("/")
        self.key = key

    def _req(
        self,
        method: str,
        path: str,
        body: Any = None,
        prefer: str | None = None,
    ) -> Any:
        req = urllib.request.Request(f"{self.url}/rest/v1/{path}", method=method)
        req.add_header("apikey", self.key)
        req.add_header("Authorization", f"Bearer {self.key}")
        req.add_header("Content-Type", "application/json")
        if prefer:
            req.add_header("Prefer", prefer)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        try:
            with urllib.request.urlopen(req, data=data, timeout=60) as r:
                raw = r.read()
                if not raw:
                    return None
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(
                f"{method} {path} -> HTTP {e.code}: {msg}"
            ) from None

    def select_all(self, table: str, columns: str = "*", filters: str = "") -> list[dict]:
        """Fetch every row of a table (paginated)."""
        out: list[dict] = []
        offset = 0
        while True:
            qs = f"select={columns}"
            if filters:
                qs += f"&{filters}"
            qs += f"&limit={PAGE}&offset={offset}&order=id.asc"
            rows = self._req("GET", f"{table}?{qs}")
            if not rows:
                return out
            out.extend(rows)
            if len(rows) < PAGE:
                return out
            offset += PAGE

    def insert_batch(self, table: str, rows: list[dict]) -> list[dict]:
        """INSERT and return the inserted rows (with ids)."""
        if not rows:
            return []
        result: list[dict] = []
        for i in range(0, len(rows), INSERT_BATCH):
            chunk = rows[i : i + INSERT_BATCH]
            inserted = self._req(
                "POST", table, body=chunk, prefer="return=representation"
            )
            if inserted:
                result.extend(inserted)
        return result

    def patch(self, table: str, row_id: int, patch: dict) -> None:
        if not patch:
            return
        self._req(
            "PATCH", f"{table}?id=eq.{row_id}", body=patch, prefer="return=minimal"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_json_field(val: Any) -> Any:
    if val is None or isinstance(val, (list, dict)):
        return val
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return val


def diff_fields(existing: dict, desired: dict, fields: list[str]) -> dict:
    """Return only the keys whose values differ between existing and desired."""
    out: dict = {}
    for k in fields:
        a = existing.get(k)
        b = desired.get(k)
        # Treat list/dict equality literally; let None == None work
        if a != b:
            out[k] = b
    return out


# ---------------------------------------------------------------------------
# Sync stages
# ---------------------------------------------------------------------------


# Columns we actively manage on each STL RV table. Anything not in this list
# is left alone (lets STL RV keep dealer-specific edits / extra columns).
MFR_COLS = [
    "name",
    "display_name",
    "parent_company",
    "headquarters",
    "website",
    "rv_types",
    "notes",
]
MODEL_COLS = [
    "manufacturer_id",
    "manufacturer_name",
    "model_year",
    "model_name",
    "series",
    "rv_class",
    "rv_type",
    "length_ft_min",
    "length_ft_max",
    "width_ft",
    "gvwr_lbs_min",
    "gvwr_lbs_max",
    "dry_weight_lbs_min",
    "dry_weight_lbs_max",
    "sleeping_capacity_min",
    "sleeping_capacity_max",
    "slideout_count_min",
    "slideout_count_max",
    "bathroom_count_min",
    "bathroom_count_max",
    "base_msrp_usd",
    "chassis",
    "engine",
    "fuel_type",
    "shore_power_amps",
    "floorplan_names",
    "notable_features",
    "source_url",
    "data_quality",
]
FLOORPLAN_COLS = [
    "model_id",
    "manufacturer_name",
    "model_name",
    "model_year",
    "floorplan_code",
    "floorplan_type",
    "length_ft",
    "width_ft",
    "interior_height_ft",
    "sleeping_capacity",
    "slideout_count",
    "bed_types",
    "bathroom_count",
    "half_bath",
    "msrp_usd",
    "standard_features",
    "source_url",
]
IMAGE_COLS = [
    "model_id",
    "manufacturer",
    "model_name",
    "image_type",
    "source_url",
]


def sync_manufacturers(
    sql: sqlite3.Connection, supa: Supa, dry_run: bool, slug_filter: str | None
) -> dict[str, int]:
    """Returns {mfr_slug -> stl_rv_manufacturer_id} after sync."""
    print("\n=== manufacturers ===")
    cur = sql.cursor()
    where = " WHERE slug = ?" if slug_filter else ""
    args = (slug_filter,) if slug_filter else ()
    cur.execute(
        f"""SELECT slug, name, display_name, parent_company, headquarters,
                   website, rv_types, notes
            FROM manufacturers{where} ORDER BY slug""",
        args,
    )
    src_rows = [dict(zip(
        ["slug", "name", "display_name", "parent_company", "headquarters",
         "website", "rv_types", "notes"], r,
    )) for r in cur.fetchall()]
    print(f"  rv-catalog: {len(src_rows)} mfrs")

    existing = supa.select_all("manufacturers")
    by_name = {r["name"]: r for r in existing}
    print(f"  STL RV:     {len(existing)} mfrs")

    inserts, updates = 0, 0
    new_rows: list[dict] = []
    for src in src_rows:
        desired = {
            "name": src["name"],
            "display_name": src["display_name"],
            "parent_company": src["parent_company"],
            "headquarters": src["headquarters"],
            "website": src["website"],
            "rv_types": parse_json_field(src["rv_types"]),
            "notes": src["notes"],
        }
        existing_row = by_name.get(src["name"])
        if existing_row is None:
            new_rows.append(desired)
            inserts += 1
        else:
            patch = diff_fields(existing_row, desired, MFR_COLS)
            if patch:
                updates += 1
                if not dry_run:
                    supa.patch("manufacturers", existing_row["id"], patch)

    if not dry_run and new_rows:
        inserted = supa.insert_batch("manufacturers", new_rows)
        for row in inserted:
            by_name[row["name"]] = row

    print(f"  inserts={inserts}  updates={updates}  ({'dry-run' if dry_run else 'applied'})")

    # Build slug -> stl_rv_id map. Need name to be unique; rv-catalog keeps it.
    name_to_id = {r["name"]: r["id"] for r in by_name.values()}
    return {
        src["slug"]: name_to_id.get(src["name"])
        for src in src_rows
        if name_to_id.get(src["name"]) is not None
    }


def sync_models(
    sql: sqlite3.Connection,
    supa: Supa,
    dry_run: bool,
    slug_to_mfrid: dict[str, int],
    slug_filter: str | None,
) -> dict[int, int]:
    """Returns {rv_catalog_model_id -> stl_rv_model_id} for floorplan/image FK."""
    print("\n=== models ===")
    cur = sql.cursor()

    cols = (
        "id, manufacturer_slug, model_year, model_name, series, rv_class, rv_type, "
        "length_ft_min, length_ft_max, width_ft, gvwr_lbs_min, gvwr_lbs_max, "
        "dry_weight_lbs_min, dry_weight_lbs_max, sleeping_capacity_min, "
        "sleeping_capacity_max, slideout_count_min, slideout_count_max, "
        "bathroom_count_min, bathroom_count_max, base_msrp_usd, chassis, engine, "
        "fuel_type, shore_power_amps, floorplan_names, notable_features, "
        "source_url, data_quality"
    )
    where = " WHERE manufacturer_slug = ?" if slug_filter else ""
    args = (slug_filter,) if slug_filter else ()
    cur.execute(f"SELECT {cols} FROM models{where} ORDER BY id", args)
    src_rows = [dict(zip([c.strip() for c in cols.split(",")], r)) for r in cur.fetchall()]
    print(f"  rv-catalog: {len(src_rows)} models")

    # Existing STL RV models — fetch only those we may touch (filter by mfr name).
    if slug_filter:
        # Just the relevant mfr name
        cur.execute("SELECT name FROM manufacturers WHERE slug = ?", (slug_filter,))
        mfr_names = [r[0] for r in cur.fetchall()]
        if not mfr_names:
            print("  slug filter produced no manufacturer; nothing to do")
            return {}
        in_list = ",".join(f'"{n}"' for n in mfr_names)
        existing = supa.select_all("models", filters=f"manufacturer_name=in.({in_list})")
    else:
        existing = supa.select_all("models")
    print(f"  STL RV:     {len(existing)} models")

    # Natural key: (manufacturer_id, model_name, model_year)
    by_key = {(r["manufacturer_id"], r["model_name"], r["model_year"]): r for r in existing}

    # rv-catalog manufacturer slug -> name lookup (for manufacturer_name col)
    cur.execute("SELECT slug, name FROM manufacturers")
    slug_to_name = {r[0]: r[1] for r in cur.fetchall()}

    inserts, updates, skipped_no_mfr = 0, 0, 0
    new_rows: list[dict] = []
    src_id_to_natural: dict[int, tuple] = {}

    for src in src_rows:
        slug = src["manufacturer_slug"]
        mfr_id = slug_to_mfrid.get(slug)
        if mfr_id is None:
            skipped_no_mfr += 1
            continue
        desired = {
            "manufacturer_id": mfr_id,
            "manufacturer_name": slug_to_name.get(slug),
            "model_year": src["model_year"],
            "model_name": src["model_name"],
            "series": src["series"],
            "rv_class": src["rv_class"],
            "rv_type": src["rv_type"],
            "length_ft_min": src["length_ft_min"],
            "length_ft_max": src["length_ft_max"],
            "width_ft": src["width_ft"],
            "gvwr_lbs_min": src["gvwr_lbs_min"],
            "gvwr_lbs_max": src["gvwr_lbs_max"],
            "dry_weight_lbs_min": src["dry_weight_lbs_min"],
            "dry_weight_lbs_max": src["dry_weight_lbs_max"],
            "sleeping_capacity_min": src["sleeping_capacity_min"],
            "sleeping_capacity_max": src["sleeping_capacity_max"],
            "slideout_count_min": src["slideout_count_min"],
            "slideout_count_max": src["slideout_count_max"],
            "bathroom_count_min": src["bathroom_count_min"],
            "bathroom_count_max": src["bathroom_count_max"],
            "base_msrp_usd": src["base_msrp_usd"],
            "chassis": src["chassis"],
            "engine": src["engine"],
            "fuel_type": src["fuel_type"],
            "shore_power_amps": src["shore_power_amps"],
            "floorplan_names": parse_json_field(src["floorplan_names"]),
            "notable_features": parse_json_field(src["notable_features"]),
            "source_url": src["source_url"],
            "data_quality": src["data_quality"],
        }
        key = (mfr_id, src["model_name"], src["model_year"])
        src_id_to_natural[src["id"]] = key
        existing_row = by_key.get(key)
        if existing_row is None:
            new_rows.append(desired)
            inserts += 1
        else:
            patch = diff_fields(existing_row, desired, MODEL_COLS)
            if patch:
                updates += 1
                if not dry_run:
                    supa.patch("models", existing_row["id"], patch)

    if not dry_run and new_rows:
        inserted = supa.insert_batch("models", new_rows)
        for row in inserted:
            by_key[(row["manufacturer_id"], row["model_name"], row["model_year"])] = row
    elif dry_run and new_rows:
        # Assign synthetic negative IDs so downstream floorplan/image stages
        # can preview their would-insert counts correctly.
        synthetic = -1
        for src in src_rows:
            key = src_id_to_natural.get(src["id"])
            if key and key not in by_key:
                by_key[key] = {"id": synthetic, **{c: None for c in MODEL_COLS}}
                synthetic -= 1

    print(
        f"  inserts={inserts}  updates={updates}  skipped_no_mfr={skipped_no_mfr}  "
        f"({'dry-run' if dry_run else 'applied'})"
    )

    # rv_catalog_model_id -> stl_rv_model_id (real or synthetic in dry-run)
    return {
        src_id: by_key[key]["id"]
        for src_id, key in src_id_to_natural.items()
        if by_key.get(key) and "id" in by_key[key]
    }


def sync_floorplans(
    sql: sqlite3.Connection,
    supa: Supa,
    dry_run: bool,
    src_to_stl_model_id: dict[int, int],
    slug_filter: str | None,
) -> None:
    print("\n=== floorplans ===")
    cur = sql.cursor()
    cols = (
        "id, model_id, manufacturer_slug, model_name, model_year, floorplan_code, "
        "floorplan_type, length_ft, width_ft, interior_height_ft, sleeping_capacity, "
        "slideout_count, bed_types, bathroom_count, half_bath, msrp_usd, "
        "standard_features, source_url"
    )
    where = " WHERE manufacturer_slug = ?" if slug_filter else ""
    args = (slug_filter,) if slug_filter else ()
    cur.execute(f"SELECT {cols} FROM floorplans{where} ORDER BY id", args)
    src_rows = [dict(zip([c.strip() for c in cols.split(",")], r)) for r in cur.fetchall()]
    print(f"  rv-catalog: {len(src_rows)} floorplans")

    cur.execute("SELECT slug, name FROM manufacturers")
    slug_to_name = {r[0]: r[1] for r in cur.fetchall()}

    # Pull existing only for the model_ids we may touch (avoids 553+ -> 30K row reads)
    stl_model_ids = sorted({mid for mid in src_to_stl_model_id.values()})
    existing: list[dict] = []
    for i in range(0, len(stl_model_ids), 200):
        chunk = stl_model_ids[i : i + 200]
        in_list = ",".join(str(x) for x in chunk)
        existing.extend(
            supa.select_all("floorplans", filters=f"model_id=in.({in_list})")
        )
    print(f"  STL RV:     {len(existing)} floorplans (in scope)")
    by_key = {(r["model_id"], r["floorplan_code"]): r for r in existing}

    inserts, updates, skipped_no_model = 0, 0, 0
    new_rows: list[dict] = []
    for src in src_rows:
        stl_model_id = src_to_stl_model_id.get(src["model_id"])
        if stl_model_id is None:
            skipped_no_model += 1
            continue
        desired = {
            "model_id": stl_model_id,
            "manufacturer_name": slug_to_name.get(src["manufacturer_slug"]),
            "model_name": src["model_name"],
            "model_year": src["model_year"],
            "floorplan_code": src["floorplan_code"],
            "floorplan_type": src["floorplan_type"],
            "length_ft": src["length_ft"],
            "width_ft": src["width_ft"],
            "interior_height_ft": src["interior_height_ft"],
            "sleeping_capacity": src["sleeping_capacity"],
            "slideout_count": src["slideout_count"],
            "bed_types": parse_json_field(src["bed_types"]),
            "bathroom_count": src["bathroom_count"],
            "half_bath": src["half_bath"],
            "msrp_usd": src["msrp_usd"],
            "standard_features": parse_json_field(src["standard_features"]),
            "source_url": src["source_url"],
        }
        key = (stl_model_id, src["floorplan_code"])
        existing_row = by_key.get(key)
        if existing_row is None:
            new_rows.append(desired)
            inserts += 1
        else:
            patch = diff_fields(existing_row, desired, FLOORPLAN_COLS)
            if patch:
                updates += 1
                if not dry_run:
                    supa.patch("floorplans", existing_row["id"], patch)

    if not dry_run and new_rows:
        supa.insert_batch("floorplans", new_rows)

    print(
        f"  inserts={inserts}  updates={updates}  skipped_no_model={skipped_no_model}  "
        f"({'dry-run' if dry_run else 'applied'})"
    )


def sync_images(
    sql: sqlite3.Connection,
    supa: Supa,
    dry_run: bool,
    src_to_stl_model_id: dict[int, int],
    slug_filter: str | None,
) -> None:
    print("\n=== kb_images ===")
    cur = sql.cursor()
    cols = (
        "model_id, manufacturer_slug, model_name, image_type, source_url, "
        "width_px, height_px, file_size_bytes"
    )
    where = " WHERE manufacturer_slug = ?" if slug_filter else ""
    args = (slug_filter,) if slug_filter else ()
    cur.execute(f"SELECT {cols} FROM images{where} ORDER BY id", args)
    src_rows = [dict(zip([c.strip() for c in cols.split(",")], r)) for r in cur.fetchall()]
    print(f"  rv-catalog: {len(src_rows)} images")

    cur.execute("SELECT slug, display_name FROM manufacturers")
    slug_to_display = {r[0]: r[1] for r in cur.fetchall()}

    stl_model_ids = sorted({mid for mid in src_to_stl_model_id.values()})
    existing: list[dict] = []
    for i in range(0, len(stl_model_ids), 200):
        chunk = stl_model_ids[i : i + 200]
        in_list = ",".join(str(x) for x in chunk)
        existing.extend(
            supa.select_all("kb_images", filters=f"model_id=in.({in_list})")
        )
    print(f"  STL RV:     {len(existing)} images (in scope)")
    by_key = {(r["model_id"], r["source_url"]): r for r in existing}

    inserts, updates, skipped_no_model = 0, 0, 0
    new_rows: list[dict] = []
    for src in src_rows:
        stl_model_id = src_to_stl_model_id.get(src["model_id"])
        if stl_model_id is None:
            skipped_no_model += 1
            continue
        desired = {
            "model_id": stl_model_id,
            "manufacturer": slug_to_display.get(src["manufacturer_slug"]),
            "model_name": src["model_name"],
            "image_type": src["image_type"],
            "source_url": src["source_url"],
            "width_px": src["width_px"],
            "height_px": src["height_px"],
            "file_size_bytes": src["file_size_bytes"],
        }
        key = (stl_model_id, src["source_url"])
        existing_row = by_key.get(key)
        if existing_row is None:
            new_rows.append(desired)
            inserts += 1
        else:
            patch = diff_fields(
                existing_row,
                desired,
                IMAGE_COLS + ["width_px", "height_px", "file_size_bytes"],
            )
            if patch:
                updates += 1
                if not dry_run:
                    supa.patch("kb_images", existing_row["id"], patch)

    if not dry_run and new_rows:
        supa.insert_batch("kb_images", new_rows)

    print(
        f"  inserts={inserts}  updates={updates}  skipped_no_model={skipped_no_model}  "
        f"({'dry-run' if dry_run else 'applied'})"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Diff only, no writes")
    ap.add_argument("--slug", help="Limit to a single manufacturer slug")
    ap.add_argument(
        "--skip-images",
        action="store_true",
        help="Skip kb_images sync (the long tail). Useful for fast iteration.",
    )
    ap.add_argument(
        "--db",
        default=str(DB_PATH),
        help=f"rv-catalog SQLite path (default: {DB_PATH})",
    )
    args = ap.parse_args()

    url = os.getenv("SUPABASE_URL", DEFAULT_SUPABASE_URL)
    key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    if not key:
        print("ERROR: SUPABASE_SERVICE_KEY env var not set", file=sys.stderr)
        return 1

    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"ERROR: rv-catalog DB not found: {db_path}", file=sys.stderr)
        return 1

    supa = Supa(url, key)
    sql = sqlite3.connect(db_path)

    print(f"sync rv-catalog ({db_path}) -> STL RV ({url})")
    print(f"mode: {'DRY-RUN' if args.dry_run else 'APPLY'}"
          f"{f', slug={args.slug}' if args.slug else ''}"
          f"{', skip-images' if args.skip_images else ''}")
    started = time.time()

    slug_to_mfrid = sync_manufacturers(sql, supa, args.dry_run, args.slug)
    src_to_stl_model = sync_models(sql, supa, args.dry_run, slug_to_mfrid, args.slug)
    sync_floorplans(sql, supa, args.dry_run, src_to_stl_model, args.slug)
    if not args.skip_images:
        sync_images(sql, supa, args.dry_run, src_to_stl_model, args.slug)

    print(f"\nDone in {time.time() - started:.1f}s")
    sql.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
