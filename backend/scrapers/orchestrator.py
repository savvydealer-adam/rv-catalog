"""Orchestrates parallel scraping of multiple manufacturers."""

from __future__ import annotations

import asyncio
import json
import time

from backend.database import get_db
from backend.scrapers.base import GenericScraper


async def scrape_manufacturer(slug: str, base_url: str) -> dict:
    """Scrape a single manufacturer and log the run."""
    db = get_db()
    mfr = db.execute("SELECT id FROM manufacturers WHERE slug = ?", (slug,)).fetchone()
    if not mfr:
        db.close()
        return {"slug": slug, "error": "Manufacturer not found"}
    mfr_id = mfr["id"]

    # Create scrape run
    cursor = db.execute(
        """INSERT INTO scrape_runs (manufacturer_id, manufacturer_slug, status)
           VALUES (?, ?, 'running')""",
        (mfr_id, slug),
    )
    run_id = cursor.lastrowid
    db.execute(
        "UPDATE manufacturers SET scrape_status = 'in_progress' WHERE slug = ?",
        (slug,),
    )
    db.commit()
    db.close()

    # Run the scraper
    scraper = GenericScraper(slug, base_url)
    stats = await scraper.run(max_models=25)

    # Update run with results
    db = get_db()
    status = "success" if stats["models_extracted"] > 0 else "partial"
    if stats.get("errors") and stats["models_extracted"] == 0:
        status = "error"

    db.execute(
        """UPDATE scrape_runs SET
           finished_at = datetime('now', 'utc'),
           status = ?,
           models_found = ?,
           models_added = ?,
           floorplans_added = ?,
           images_downloaded = ?,
           errors = ?,
           duration_s = ?
           WHERE id = ?""",
        (
            status,
            stats.get("models_found", 0),
            stats.get("models_extracted", 0),
            stats.get("floorplans_added", 0),
            stats.get("images_found", 0),
            json.dumps(stats.get("errors", []))[:2000],
            stats.get("duration_s", 0),
            run_id,
        ),
    )
    # Update manufacturer's final status
    final_status = "complete" if stats["models_extracted"] >= 3 else "partial"
    if status == "error":
        final_status = "error"
    db.execute(
        "UPDATE manufacturers SET scrape_status = ? WHERE slug = ?",
        (final_status, slug),
    )
    db.commit()
    db.close()

    return stats


async def run_wave(tier: str, concurrency: int = 3) -> list[dict]:
    """Run all manufacturers in a given tier in parallel."""
    db = get_db()
    rows = db.execute(
        "SELECT slug, website FROM manufacturers WHERE tier = ? ORDER BY scrape_priority",
        (tier,),
    ).fetchall()
    db.close()

    targets = [(r["slug"], r["website"]) for r in rows if r["website"]]
    print(f"Scraping {len(targets)} manufacturers from {tier}, concurrency={concurrency}")

    sem = asyncio.Semaphore(concurrency)

    async def bounded(slug, url):
        async with sem:
            print(f"  -> {slug} ({url})")
            start = time.time()
            result = await scrape_manufacturer(slug, url)
            dur = time.time() - start
            print(f"  <- {slug} ({dur:.1f}s) "
                  f"models={result.get('models_extracted', 0)} "
                  f"fps={result.get('floorplans_added', 0)} "
                  f"errs={len(result.get('errors', []))}")
            return result

    return await asyncio.gather(*[bounded(s, u) for s, u in targets])


async def run_all() -> list[dict]:
    """Run all manufacturers (respecting priority tiers)."""
    results = []
    for tier in ["wave_1", "wave_2", "wave_3", "wave_4"]:
        tier_results = await run_wave(tier, concurrency=3)
        results.extend(tier_results)
    return results
