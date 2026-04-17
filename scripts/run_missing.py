"""Scrape every manufacturer with zero models.

Uses IPRoyal automatically via base.py / playwright_fetcher.py when
CD_IPROYAL_USER/CD_IPROYAL_PASS are set.

Brands flagged `defunct=1` in the manufacturers table are skipped by default
(dead domain / expired SSL / repurposed site). Pass --include-defunct to
force-include them if you think they've come back online.

  python scripts/run_missing.py               # all 0-model, non-defunct brands
  python scripts/run_missing.py --concurrency 4
  python scripts/run_missing.py --skip renegade,redwood,encore
  python scripts/run_missing.py --dry-run     # just print targets, don't scrape
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


def load_targets(skip: set[str], include_defunct: bool = False) -> list[tuple[str, str]]:
    db = get_db()
    defunct_clause = "" if include_defunct else " AND COALESCE(m.defunct, 0) = 0"
    rows = db.execute(f"""
      SELECT m.slug, m.website
      FROM manufacturers m
      LEFT JOIN models md ON md.manufacturer_id = m.id
      WHERE m.website IS NOT NULL AND m.website != ''
      {defunct_clause}
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
    ap.add_argument("--include-defunct", action="store_true",
                    help="Include brands flagged defunct in the DB (default: skip)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the target list and exit without scraping")
    args = ap.parse_args()

    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    targets = load_targets(skip, include_defunct=args.include_defunct)
    if only:
        targets = [t for t in targets if t[0] in only]

    if args.dry_run:
        print(f"Would scrape {len(targets)} brands "
              f"(include_defunct={args.include_defunct}, skip={sorted(skip) or None}, "
              f"only={sorted(only) or None}):")
        for slug, url in targets:
            print(f"  {slug:30s} {url}")
        return

    if not os.getenv("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY env var not set")
        sys.exit(1)

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
