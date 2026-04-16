"""Scrape every manufacturer with zero models.

Uses IPRoyal automatically via base.py / playwright_fetcher.py when
CD_IPROYAL_USER/CD_IPROYAL_PASS are set.

  python scripts/run_missing.py               # all 0-model brands
  python scripts/run_missing.py --concurrency 4
  python scripts/run_missing.py --skip renegade,redwood,encore
"""

from __future__ import annotations

import argparse
import asyncio
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


def load_targets(skip: set[str]) -> list[tuple[str, str]]:
    db = get_db()
    rows = db.execute("""
      SELECT m.slug, m.website
      FROM manufacturers m
      LEFT JOIN models md ON md.manufacturer_id = m.id
      WHERE m.website IS NOT NULL AND m.website != ''
      GROUP BY m.id
      HAVING COUNT(md.id) = 0
      ORDER BY m.tier, m.scrape_priority
    """).fetchall()
    db.close()
    return [(r["slug"], r["website"]) for r in rows if r["slug"] not in skip]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--skip", default="",
                    help="Comma-separated slugs to skip")
    ap.add_argument("--only", default="",
                    help="Comma-separated slugs — restrict to this set")
    args = ap.parse_args()

    if not os.getenv("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY env var not set")
        sys.exit(1)

    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    targets = load_targets(skip)
    if only:
        targets = [t for t in targets if t[0] in only]
    proxy_on = bool(os.getenv("CD_IPROYAL_USER") and os.getenv("CD_IPROYAL_PASS"))
    print(f"Scraping {len(targets)} brands (concurrency={args.concurrency}, "
          f"iproyal={'on' if proxy_on else 'off'})")

    sem = asyncio.Semaphore(args.concurrency)
    results = []

    async def bounded(slug, url):
        async with sem:
            print(f"  -> {slug:30s} {url}")
            start = time.time()
            res = await scrape_manufacturer(slug, url)
            dur = time.time() - start
            print(f"  <- {slug:30s} "
                  f"models={res.get('models_extracted', 0):>3} "
                  f"fps={res.get('floorplans_added', 0):>3} "
                  f"imgs={res.get('images_found', 0):>3} "
                  f"errs={len(res.get('errors', [])):>2} "
                  f"({dur:.0f}s)")
            results.append(res)
            return res

    await asyncio.gather(*[bounded(s, u) for s, u in targets])

    succ = sum(1 for r in results if r.get("models_extracted", 0) > 0)
    total_models = sum(r.get("models_extracted", 0) for r in results)
    total_fps = sum(r.get("floorplans_added", 0) for r in results)
    print(f"\nDone. {succ}/{len(results)} brands produced data — "
          f"{total_models} models, {total_fps} floorplans")


if __name__ == "__main__":
    asyncio.run(main())
