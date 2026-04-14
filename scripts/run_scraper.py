"""CLI entry point for running the scraper.

Usage:
  python scripts/run_scraper.py --wave wave_1
  python scripts/run_scraper.py --slug keystone
  python scripts/run_scraper.py --all
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.scrapers.orchestrator import run_wave, run_all, scrape_manufacturer
from backend.database import get_db


async def run_single(slug: str):
    db = get_db()
    row = db.execute(
        "SELECT slug, website FROM manufacturers WHERE slug = ?", (slug,)
    ).fetchone()
    db.close()
    if not row:
        print(f"Manufacturer '{slug}' not found")
        return
    return await scrape_manufacturer(row["slug"], row["website"])


def main():
    parser = argparse.ArgumentParser(description="RV Catalog scraper runner")
    parser.add_argument("--wave", help="Run a specific tier: wave_1, wave_2, wave_3, wave_4")
    parser.add_argument("--slug", help="Run a single manufacturer by slug")
    parser.add_argument("--all", action="store_true", help="Run all manufacturers")
    args = parser.parse_args()

    if not os.getenv("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY env var not set")
        sys.exit(1)

    if args.slug:
        result = asyncio.run(run_single(args.slug))
        print(f"\nResult: {result}")
    elif args.wave:
        results = asyncio.run(run_wave(args.wave))
        success = sum(1 for r in results if r.get("models_extracted", 0) > 0)
        print(f"\nDone: {success}/{len(results)} manufacturers produced data")
    elif args.all:
        results = asyncio.run(run_all())
        success = sum(1 for r in results if r.get("models_extracted", 0) > 0)
        print(f"\nDone: {success}/{len(results)} manufacturers produced data")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
