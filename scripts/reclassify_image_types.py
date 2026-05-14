"""Backfill image_type on existing rows using the URL classifier.

All historic rows were inserted with image_type='exterior' (the previous
hardcoded default). The scraper now classifies per-URL; this script applies
the same classifier to the existing catalog so STL RV's
/api/floorplans/find-image can find floorplan-typed images for already-
scraped brands without waiting for a re-scrape.

Usage:
  python scripts/reclassify_image_types.py --dry-run
  python scripts/reclassify_image_types.py            # apply
  python scripts/reclassify_image_types.py --slug jayco
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

# Importing the scraper class transitively requires Gemini env vars etc., so
# inline the same classifier to keep this script standalone.
def classify(url: str) -> str:
    """Mirror of GenericScraper._classify_image_type. Keep these in sync."""
    u = url.lower()
    if "interior" in u:
        return "exterior"
    path = u.split("?", 1)[0]
    filename = path.rsplit("/", 1)[-1]
    if (
        "floorplan" in filename
        or "floor-plan" in filename
        or "floor_plan" in filename
        or "_fp_" in filename
        or "-fp-" in filename
    ):
        return "floorplan"
    if "/floorplans/" in u or "/floor-plans/" in u or "/floor_plans/" in u:
        return "floorplan"
    if "/floorplan/" in u or "/floor-plan/" in u or "/floor_plan/" in u:
        if not any(
            tok in filename
            for tok in (
                "paint", "graphics", "decor", "swatch", "lifestyle",
                "-img-", "_img-", "img_",
            )
        ):
            return "floorplan"
    return "exterior"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--slug", help="Limit to one manufacturer slug")
    ap.add_argument(
        "--db",
        default=str(Path(__file__).resolve().parents[1] / "data" / "rv_catalog.db"),
    )
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    where = "WHERE manufacturer_slug = ?" if args.slug else ""
    params = (args.slug,) if args.slug else ()

    rows = cur.execute(
        f"SELECT id, source_url, image_type FROM images {where}", params
    ).fetchall()
    print(f"Scanning {len(rows)} images" + (f" for {args.slug}" if args.slug else ""))

    flips = 0
    by_slug: dict[str, int] = {}
    updates: list[tuple[str, int]] = []
    for row_id, url, current in rows:
        desired = classify(url or "")
        if desired != current:
            flips += 1
            updates.append((desired, row_id))

    if args.slug is None:
        # Per-mfr breakdown of the projected flips
        cur.execute(
            f"""SELECT manufacturer_slug, COUNT(*) FROM images
                WHERE id IN ({','.join('?' * len(updates))})
                GROUP BY manufacturer_slug ORDER BY 2 DESC""",
            tuple(rid for _, rid in updates),
        ) if updates else None
        if updates:
            ids = tuple(rid for _, rid in updates)
            # SQLite has a parameter limit (~999). Use a temporary table for
            # large lists.
            if len(ids) > 800:
                cur.execute("CREATE TEMP TABLE _flip_ids (id INTEGER PRIMARY KEY)")
                cur.executemany("INSERT INTO _flip_ids VALUES (?)", [(i,) for i in ids])
                breakdown = cur.execute(
                    """SELECT i.manufacturer_slug, COUNT(*)
                       FROM images i JOIN _flip_ids f ON f.id = i.id
                       GROUP BY i.manufacturer_slug ORDER BY 2 DESC LIMIT 25"""
                ).fetchall()
                cur.execute("DROP TABLE _flip_ids")
            else:
                breakdown = cur.execute(
                    f"""SELECT manufacturer_slug, COUNT(*) FROM images
                        WHERE id IN ({','.join('?' * len(ids))})
                        GROUP BY manufacturer_slug ORDER BY 2 DESC LIMIT 25""",
                    ids,
                ).fetchall()
            print("\nTop manufacturers gaining floorplan-typed rows:")
            for slug, n in breakdown:
                print(f"  {slug:25} {n}")
                by_slug[slug] = n

    print(f"\nWould flip {flips} rows exterior -> floorplan ({'dry-run' if args.dry_run else 'applying'})")

    if updates and not args.dry_run:
        cur.executemany(
            "UPDATE images SET image_type = ? WHERE id = ?", updates
        )
        conn.commit()
        print(f"  Updated {cur.rowcount} rows.")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
