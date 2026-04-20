"""2026-04-20 round 7 — medium-brand mop-up. 5-15 model brands still not
re-scraped post-IPRoyal-bypass.
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
    ("entegra", "8 m, 12.1 img/m"),
    ("taxa", "8 m, 12.1 img/m"),
    ("drv", "19 m, 12 fp only — fp discovery under-performed"),
    ("midwest-auto", "9 m, 12.2 img/m"),
    ("starcraft", "5 m, 14.4 img/m"),
    ("american-coach", "6 m, 14.5 img/m"),
    ("storyteller", "11 m, 14.5 img/m"),
    ("nucamp", "6 m, 15.2 img/m"),
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
        print(f"  {s:18} models={c['models']:>3} fp={c['fp']:>4} img={c['img']:>5}", flush=True)

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
            f"{s:18} {b['models']:>3}->{a['models']:<3}(+{dm:<3}) "
            f"{b['fp']:>4}->{a['fp']:<4}(+{df:<3}) "
            f"{b['img']:>5}->{a['img']:<5}(+{di:<4})",
            flush=True,
        )

    print(f"\nTOTALS +{tot['models']} models, +{tot['fp']} floorplans, +{tot['img']} images", flush=True)

    out = Path(__file__).resolve().parent / "logs" / f"enrich_r7_{int(time.time())}.json"
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
