"""One-off enrichment runner for brands with thin coverage.

Re-scrapes a chosen set of manufacturers with updated brand_configs entries.
Relies on INSERT OR IGNORE in base.py._persist so existing rows are preserved.
Runs up to 3 scrapers at a time, tolerates SQLite locks (WAL + busy_timeout
already configured), and prints a before/after delta per brand.
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
    # (slug, "why")
    ("highland-ridge", "7 models, 0 floorplans"),
    ("drv", "1 model only, 0 floorplans"),
    ("happier-camper", "7 models, 2 floorplans"),
    ("roadtrek", "5 models, 2 floorplans"),
    ("airstream", "39 models, 16 floorplans"),
    ("lance", "22 models, 9 floorplans"),
    ("newmar", "14 models, 0 images"),
    ("northwood", "6 models, 4 floorplans"),
    ("taxa", "3 models, 2 floorplans"),
    ("winnebago", "22 models, 15 floorplans"),
    ("jayco", "25 models, 0.84 fp/model, 20 images"),
    ("pleasure-way", "11 models, 10 floorplans"),
    ("stealth", "12 models, 4 images"),
    ("work-and-play", "6 models, 4 images"),
    ("cedar-creek", "8 models, 9 images"),
    ("cardinal", "11 models, 14 images"),
]


def snapshot(slugs: list[str]) -> dict[str, dict]:
    db = get_db()
    out = {}
    for s in slugs:
        r = db.execute(
            "SELECT model_count, floorplan_count, image_count FROM manufacturers WHERE slug = ?",
            (s,),
        ).fetchone()
        if r:
            out[s] = {
                "models": r["model_count"] or 0,
                "fp": r["floorplan_count"] or 0,
                "img": r["image_count"] or 0,
            }
    db.close()
    return out


async def run_one(slug: str, reason: str):
    db = get_db()
    row = db.execute(
        "SELECT website FROM manufacturers WHERE slug = ?", (slug,)
    ).fetchone()
    db.close()
    if not row:
        return {"slug": slug, "error": "not found"}
    try:
        t0 = time.time()
        stats = await scrape_manufacturer(slug, row["website"])
        stats["wall_s"] = round(time.time() - t0, 1)
        stats["reason"] = reason
        return stats
    except Exception as e:
        return {"slug": slug, "error": str(e)[:200], "reason": reason}


async def main():
    if not os.getenv("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY not set")
        sys.exit(1)

    slugs = [s for s, _ in TARGETS]
    before = snapshot(slugs)
    print("=== BEFORE ===")
    for s in slugs:
        b = before.get(s, {})
        print(f"  {s:20} models={b.get('models',0):>3} fp={b.get('fp',0):>3} img={b.get('img',0):>4}")

    # Run up to 3 in parallel to avoid slamming Gemini API + IPRoyal
    sem = asyncio.Semaphore(3)

    async def guarded(slug, reason):
        async with sem:
            print(f"[start] {slug} ({reason})", flush=True)
            r = await run_one(slug, reason)
            print(f"[done]  {slug} -> extracted={r.get('models_extracted','?')} fp+={r.get('floorplans_added','?')} img={r.get('images_found','?')} errs={len(r.get('errors') or [])}", flush=True)
            return r

    results = await asyncio.gather(*[guarded(s, r) for s, r in TARGETS])

    after = snapshot(slugs)
    print("\n=== AFTER (delta) ===")
    print(f"{'slug':20} {'models':>12} {'fp':>12} {'img':>12}")
    totals = {"models": 0, "fp": 0, "img": 0}
    for s in slugs:
        b = before.get(s, {"models": 0, "fp": 0, "img": 0})
        a = after.get(s, {"models": 0, "fp": 0, "img": 0})
        dm = a["models"] - b["models"]
        df = a["fp"] - b["fp"]
        di = a["img"] - b["img"]
        totals["models"] += dm
        totals["fp"] += df
        totals["img"] += di
        print(
            f"{s:20} {b['models']}->{a['models']} (+{dm}) ".ljust(40)
            + f"{b['fp']}->{a['fp']} (+{df}) ".ljust(20)
            + f"{b['img']}->{a['img']} (+{di})"
        )
    print(f"\nTOTALS +{totals['models']} models, +{totals['fp']} floorplans, +{totals['img']} images")

    # Write delta file for use in PLAN.md update
    out = Path(__file__).resolve().parent / "logs" / f"enrich_{int(time.time())}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "before": before,
                "after": after,
                "totals": totals,
                "results": [
                    {
                        k: (v if not isinstance(v, list) else v[:5])
                        for k, v in r.items()
                    }
                    for r in results
                ],
            },
            indent=2,
            default=str,
        )
    )
    print(f"Wrote delta to {out}")


if __name__ == "__main__":
    asyncio.run(main())
