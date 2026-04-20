"""2026-04-20 round 5 — big-brand image backfill. After rounds 2-4 cleaned
up all the low-img/m small brands, this targets brands with >=10 models
that still have an img-per-model ratio under 10.
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
    ("thor-motor-coach", "38 m, 4.9 img/m — already force_stealth but pre-CDN-fix"),
    ("northwood", "18 m, 4.9 img/m"),
    ("stealth", "17 m, 5 img/m"),
    ("pleasure-way", "16 m, 6.3 img/m"),
    ("aliner", "24 m, 7.9 img/m"),
    ("lance", "57 m, 8.2 img/m"),
    ("keystone", "18 m, 8.7 img/m"),
    ("cardinal", "18 m, 9.7 img/m"),
]


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
    before = {s: counter_snapshot(s) for s in slugs}
    print("=== BEFORE ===", flush=True)
    for s in slugs:
        c = before[s]
        print(f"  {s:20} models={c['models']:>3} fp={c['fp']:>4} img={c['img']:>5}", flush=True)

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

    after = {s: counter_snapshot(s) for s in slugs}
    print("\n=== AFTER ===", flush=True)
    tot = {"models": 0, "fp": 0, "img": 0}
    for s in slugs:
        b, a = before[s], after[s]
        dm, df, di = a["models"] - b["models"], a["fp"] - b["fp"], a["img"] - b["img"]
        tot["models"] += dm
        tot["fp"] += df
        tot["img"] += di
        print(
            f"{s:20} {b['models']:>3}->{a['models']:<3}(+{dm:<3}) "
            f"{b['fp']:>4}->{a['fp']:<4}(+{df:<3}) "
            f"{b['img']:>5}->{a['img']:<5}(+{di:<4})",
            flush=True,
        )

    print(f"\nTOTALS +{tot['models']} models, +{tot['fp']} floorplans, +{tot['img']} images", flush=True)

    out = Path(__file__).resolve().parent / "logs" / f"enrich_r5_{int(time.time())}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(
        json.dumps(
            {"before": before, "after": after, "totals": tot, "results": results},
            indent=2, default=str,
        )
    )
    print(f"[log] {out}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
