"""Backup the RV catalog DB to markdown files.

Creates:
  backups/<date>/SUMMARY.md                  -- overall stats
  backups/<date>/manufacturers.md            -- all manufacturers table
  backups/<date>/manufacturers/<slug>.md     -- per-brand detail
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.database import get_db

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def fmt_int(v) -> str:
    return f"{v:,}" if v is not None else "—"


def fmt_money(v) -> str:
    return f"${v:,}" if v is not None else "—"


def fmt_range(lo, hi, suffix="") -> str:
    if lo is None and hi is None:
        return "—"
    if lo == hi or hi is None:
        return f"{lo}{suffix}"
    if lo is None:
        return f"≤{hi}{suffix}"
    return f"{lo}–{hi}{suffix}"


def write_summary(out_dir: Path, db: sqlite3.Connection) -> None:
    total_mfrs = db.execute("SELECT COUNT(*) FROM manufacturers").fetchone()[0]
    with_data = db.execute("SELECT COUNT(*) FROM manufacturers WHERE model_count >= 1").fetchone()[0]
    total_models = db.execute("SELECT COUNT(*) FROM models").fetchone()[0]
    total_fps = db.execute("SELECT COUNT(*) FROM floorplans").fetchone()[0]
    total_images = db.execute("SELECT COUNT(*) FROM images").fetchone()[0]

    lines = [
        f"# RV Catalog Backup — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Totals",
        "",
        f"- **Manufacturers:** {total_mfrs} ({with_data} with data, {with_data * 100 // total_mfrs}%)",
        f"- **Models:** {total_models:,}",
        f"- **Floorplans:** {total_fps:,}",
        f"- **Images:** {total_images:,}",
        "",
        "## By Wave",
        "",
        "| Wave | Total | With Data | Models | Floorplans |",
        "|------|-------|-----------|--------|------------|",
    ]
    for row in db.execute(
        """SELECT tier, COUNT(*) as total,
                  SUM(CASE WHEN model_count >= 1 THEN 1 ELSE 0 END) as with_data,
                  SUM(model_count) as models, SUM(floorplan_count) as fps
           FROM manufacturers GROUP BY tier ORDER BY tier"""
    ):
        lines.append(
            f"| {row['tier']} | {row['total']} | {row['with_data']} | "
            f"{fmt_int(row['models'])} | {fmt_int(row['fps'])} |"
        )

    lines += ["", "## By Parent Company", "",
              "| Parent | Brands | With Data | Models | Floorplans |",
              "|--------|--------|-----------|--------|------------|"]
    for row in db.execute(
        """SELECT parent_company, COUNT(*) as total,
                  SUM(CASE WHEN model_count >= 1 THEN 1 ELSE 0 END) as with_data,
                  SUM(model_count) as models, SUM(floorplan_count) as fps
           FROM manufacturers GROUP BY parent_company ORDER BY SUM(model_count) DESC"""
    ):
        lines.append(
            f"| {row['parent_company']} | {row['total']} | {row['with_data']} | "
            f"{fmt_int(row['models'])} | {fmt_int(row['fps'])} |"
        )

    lines += ["", "## Top 25 Brands by Model Count", "",
              "| Brand | Parent | Tier | Models | Floorplans | Images |",
              "|-------|--------|------|--------|------------|--------|"]
    for row in db.execute(
        """SELECT display_name, parent_company, tier, model_count, floorplan_count, image_count
           FROM manufacturers WHERE model_count >= 1
           ORDER BY model_count DESC LIMIT 25"""
    ):
        lines.append(
            f"| [{row['display_name']}](manufacturers/{_slugify(row['display_name'])}.md) | "
            f"{row['parent_company']} | {row['tier']} | "
            f"{row['model_count']} | {row['floorplan_count']} | {row['image_count']} |"
        )

    lines += ["", "## Remaining Failures", ""]
    for tier_name in ["wave_1", "wave_2", "wave_3", "wave_4"]:
        failures = list(db.execute(
            """SELECT display_name, website FROM manufacturers
               WHERE tier = ? AND model_count = 0 ORDER BY scrape_priority""",
            (tier_name,),
        ))
        if not failures:
            continue
        lines.append(f"### {tier_name} ({len(failures)})")
        lines.append("")
        for f in failures:
            lines.append(f"- **{f['display_name']}** — {f['website']}")
        lines.append("")

    (out_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def write_all_manufacturers_table(out_dir: Path, db: sqlite3.Connection) -> None:
    lines = [
        "# All Manufacturers",
        "",
        "| Brand | Parent | Tier | Status | Models | Floorplans | Images | Website |",
        "|-------|--------|------|--------|--------|------------|--------|---------|",
    ]
    for row in db.execute(
        """SELECT slug, display_name, parent_company, tier, scrape_status,
                  model_count, floorplan_count, image_count, website
           FROM manufacturers ORDER BY scrape_priority"""
    ):
        detail_link = f"manufacturers/{row['slug']}.md" if row['model_count'] >= 1 else ""
        name_cell = f"[{row['display_name']}]({detail_link})" if detail_link else row['display_name']
        lines.append(
            f"| {name_cell} | {row['parent_company']} | {row['tier']} | "
            f"{row['scrape_status']} | {row['model_count']} | {row['floorplan_count']} | "
            f"{row['image_count']} | {row['website']} |"
        )
    (out_dir / "manufacturers.md").write_text("\n".join(lines), encoding="utf-8")


def write_manufacturer_detail(out_dir: Path, db: sqlite3.Connection, slug: str) -> None:
    mfr = db.execute("SELECT * FROM manufacturers WHERE slug = ?", (slug,)).fetchone()
    if not mfr:
        return

    lines = [
        f"# {mfr['display_name']}",
        "",
        f"- **Parent:** {mfr['parent_company']}",
        f"- **Tier:** {mfr['tier']}",
        f"- **RV types:** {', '.join(json.loads(mfr['rv_types'] or '[]'))}",
        f"- **Website:** {mfr['website']}",
        f"- **Last scraped:** {mfr['last_scraped_at'] or '—'}",
        f"- **Counts:** {mfr['model_count']} models, {mfr['floorplan_count']} floorplans, {mfr['image_count']} images",
        "",
        "## Models",
        "",
    ]

    models = db.execute(
        "SELECT * FROM models WHERE manufacturer_slug = ? ORDER BY model_name",
        (slug,),
    ).fetchall()

    if not models:
        lines.append("_No models scraped._")
    else:
        lines += [
            "| Model | Year | Class | Type | Length (ft) | Sleeps | Slides | MSRP | Floorplans |",
            "|-------|------|-------|------|-------------|--------|--------|------|------------|",
        ]
        for m in models:
            fp_count = db.execute(
                "SELECT COUNT(*) FROM floorplans WHERE model_id = ?", (m["id"],)
            ).fetchone()[0]
            lines.append(
                f"| {m['model_name']} | {m['model_year'] or '—'} | "
                f"{m['rv_class'] or '—'} | {m['rv_type'] or '—'} | "
                f"{fmt_range(m['length_ft_min'], m['length_ft_max'])} | "
                f"{fmt_range(m['sleeping_capacity_min'], m['sleeping_capacity_max'])} | "
                f"{fmt_range(m['slideout_count_min'], m['slideout_count_max'])} | "
                f"{fmt_money(m['base_msrp_usd'])} | {fp_count} |"
            )

    # Floorplans per model
    if models:
        lines += ["", "## Floorplans by Model", ""]
        for m in models:
            fps = list(db.execute(
                "SELECT * FROM floorplans WHERE model_id = ? ORDER BY floorplan_code",
                (m["id"],),
            ))
            if not fps:
                continue
            lines.append(f"### {m['model_name']}")
            lines.append("")
            lines += [
                "| Floorplan | Length | Sleeps | Slides | Baths | Dry wt | GVWR | MSRP |",
                "|-----------|--------|--------|--------|-------|--------|------|------|",
            ]
            for f in fps:
                lines.append(
                    f"| {f['floorplan_code']} | "
                    f"{f['length_ft'] or '—'} | {f['sleeping_capacity'] or '—'} | "
                    f"{f['slideout_count'] or '—'} | {f['bathroom_count'] or '—'} | "
                    f"{fmt_int(f['dry_weight_lbs'])} | {fmt_int(f['gvwr_lbs'])} | "
                    f"{fmt_money(f['msrp_usd'])} |"
                )
            lines.append("")

    (out_dir / f"{slug}.md").write_text("\n".join(lines), encoding="utf-8")


def _slugify(s: str) -> str:
    return s.lower().replace(" ", "-").replace("/", "-")


def main():
    db = get_db()
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_root = PROJECT_ROOT / "backups" / date_str
    out_mfrs = out_root / "manufacturers"
    out_mfrs.mkdir(parents=True, exist_ok=True)

    print(f"Writing backup to {out_root}")
    write_summary(out_root, db)
    write_all_manufacturers_table(out_root, db)

    count = 0
    for row in db.execute("SELECT slug FROM manufacturers WHERE model_count >= 1"):
        write_manufacturer_detail(out_mfrs, db, row["slug"])
        count += 1

    db.close()
    print(f"Wrote SUMMARY.md, manufacturers.md, and {count} manufacturer detail files")
    print(f"Total files: {count + 2}")


if __name__ == "__main__":
    main()
