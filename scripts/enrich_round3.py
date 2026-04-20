"""2026-04-20 round 3 — low-image-ratio active brands that were blocked by
the IPRoyal 402 quota and never benefitted from the 04-17 image-ranker /
spec-table prompt / CDN-URL extractor fixes. Same runner shape as
enrich_spec_round.py.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import get_db
from backend.scrapers.orchestrator import scrape_manufacturer


TARGETS = [
    ("no-boundaries", "10 models, 1.3 img/m — httpx path"),
    ("riverstone", "9 models, 1.3 img/m"),
    ("vibe-rv", "10 models, 1.4 img/m"),
    ("happier-camper", "15 models, 2 img/m"),
    ("rockwood", "4 models, 4.3 img/m — likely more models"),
    ("host", "3 models, 4.7 img/m"),
    ("palomino", "2 models, 6.5 fp/m — possibly missing sibling models"),
    ("heartland", "8 models, 2.5 img/m — force_stealth, but image-ranker fix should help"),
]


def fp_spec_stats(slug: str) -> dict:
    db = get_db()
    row = db.execute(
        """SELECT COUNT(*) n,
             SUM(CASE WHEN length_ft IS NOT NULL THEN 1 ELSE 0 END) len,
             SUM(CASE WHEN sleeping_capacity IS NOT NULL THEN 1 ELSE 0 END) sleep,
             SUM(CASE WHEN dry_weight_lbs IS NOT NULL THEN 1 ELSE 0 END) dry,
             SUM(CASE WHEN gvwr_lbs IS NOT NULL THEN 1 ELSE 0 END) gvwr,
             SUM(CASE WHEN slideout_count IS NOT NULL THEN 1 ELSE 0 END) slide
           FROM floorplans f
           JOIN models m ON m.id = f.model_id
           JOIN manufacturers mf ON mf.id = m.manufacturer_id
           WHERE mf.slug = ?""",
        (slug,),
    ).fetchone()
    db.close()
    return {
        "fp": row["n"] or 0,
        "len": row["len"] or 0,
        "sleep": row["sleep"] or 0,
        "dry": row["dry"] or 0,
        "gvwr": row["gvwr"] or 0,
        "slide": row["slide"] or 0,
    }


def counter_snapshot(slug: str) -> dict:
    db = get_db()
    r = db.execute(
        "SELECT model_count, floorplan_count, image_count FROM manufacturers WHERE slug = ?",
        (slug,),
    ).fetchone()
    db.close()
    return {
        "models": (r["model_count"] or 0) if r else 0,
        "fp": (r["floorplan_count"] or 0) if r else 0,
        "img": (r["image_count"] or 0) if r else 0,
    }


async def run_one(slug: str, reason: str):
    db = get_db()
    row = db.execute(
        "SELECT website FROM manufacturers WHERE slug = ?", (slug,)
    ).fetchone()
    db.close()
    if not row:
        return {"slug": slug, "error": "not found"}
    t0 = time.time()
    try:
        stats = await scrape_manufacturer(slug, row["website"])
    except Exception as e:
        return {"slug": slug, "error": str(e)[:200], "reason": reason}
    stats["wall_s"] = round(time.time() - t0, 1)
    stats["reason"] = reason
    return stats


async def main():
    if not os.getenv("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY not set")
        sys.exit(1)

    slugs = [s for s, _ in TARGETS]
    before_counts = {s: counter_snapshot(s) for s in slugs}
    before_spec = {s: fp_spec_stats(s) for s in slugs}

    print("=== BEFORE ===", flush=True)
    for s in slugs:
        c = before_counts[s]
        sp = before_spec[s]
        print(
            f"  {s:14} models={c['models']:>3} fp={c['fp']:>3} img={c['img']:>4}  "
            f"| len={sp['len']}/{sp['fp']} sleep={sp['sleep']}/{sp['fp']} "
            f"dry={sp['dry']}/{sp['fp']} gvwr={sp['gvwr']}/{sp['fp']} slide={sp['slide']}/{sp['fp']}",
            flush=True,
        )

    sem = asyncio.Semaphore(3)

    async def guarded(slug, reason):
        async with sem:
            print(f"[start] {slug} ({reason})", flush=True)
            r = await run_one(slug, reason)
            if "error" in r:
                print(f"[err]   {slug} -> {r['error']}", flush=True)
            else:
                print(
                    f"[done]  {slug} -> extracted={r.get('models_extracted','?')} "
                    f"fp+={r.get('floorplans_added','?')} "
                    f"img={r.get('images_found','?')} "
                    f"errs={len(r.get('errors') or [])} "
                    f"wall={r.get('wall_s','?')}s",
                    flush=True,
                )
            return r

    results = await asyncio.gather(*[guarded(s, r) for s, r in TARGETS])

    after_counts = {s: counter_snapshot(s) for s in slugs}
    after_spec = {s: fp_spec_stats(s) for s in slugs}

    print("\n=== AFTER ===", flush=True)
    print(
        f"{'slug':14} {'models':>13} {'fp':>13} {'img':>13} "
        f"{'len':>10} {'sleep':>10} {'dry':>10} {'gvwr':>10} {'slide':>10}",
        flush=True,
    )
    tot = {"models": 0, "fp": 0, "img": 0}
    for s in slugs:
        b, a = before_counts[s], after_counts[s]
        bs, asp = before_spec[s], after_spec[s]
        dm, df, di = a["models"] - b["models"], a["fp"] - b["fp"], a["img"] - b["img"]
        tot["models"] += dm
        tot["fp"] += df
        tot["img"] += di
        print(
            f"{s:14} {b['models']:>3}->{a['models']:<3}(+{dm:<3}) "
            f"{b['fp']:>3}->{a['fp']:<3}(+{df:<3}) "
            f"{b['img']:>4}->{a['img']:<4}(+{di:<4}) "
            f"{bs['len']:>3}->{asp['len']:<3}  "
            f"{bs['sleep']:>3}->{asp['sleep']:<3}  "
            f"{bs['dry']:>3}->{asp['dry']:<3}  "
            f"{bs['gvwr']:>3}->{asp['gvwr']:<3}  "
            f"{bs['slide']:>3}->{asp['slide']:<3}",
            flush=True,
        )

    print(
        f"\nTOTALS +{tot['models']} models, +{tot['fp']} floorplans, +{tot['img']} images",
        flush=True,
    )

    out = Path(__file__).resolve().parent / "logs" / f"enrich_r3_{int(time.time())}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "before_counts": before_counts,
                "after_counts": after_counts,
                "before_spec": before_spec,
                "after_spec": after_spec,
                "totals": tot,
                "results": results,
            },
            indent=2,
            default=str,
        )
    )
    print(f"[log] {out}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
