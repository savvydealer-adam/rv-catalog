"""Scrape trigger + status endpoints."""

import json
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.database import get_db

router = APIRouter(prefix="/api/scrape", tags=["scrape"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRAPER_SCRIPT = PROJECT_ROOT / "scripts" / "run_scraper.py"


@router.get("/runs")
def list_runs(limit: int = 50):
    """List recent scrape runs across all manufacturers."""
    db = get_db()
    rows = db.execute(
        """SELECT r.*, m.display_name as manufacturer_name
           FROM scrape_runs r
           JOIN manufacturers m ON r.manufacturer_id = m.id
           ORDER BY r.started_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    db.close()
    return [
        {
            "id": r["id"],
            "manufacturer_slug": r["manufacturer_slug"],
            "manufacturer_name": r["manufacturer_name"],
            "started_at": r["started_at"],
            "finished_at": r["finished_at"],
            "status": r["status"],
            "models_found": r["models_found"],
            "models_added": r["models_added"],
            "floorplans_added": r["floorplans_added"],
            "images_downloaded": r["images_downloaded"],
            "duration_s": r["duration_s"],
            "errors": json.loads(r["errors"]) if r["errors"] else [],
        }
        for r in rows
    ]


@router.get("/active")
def list_active():
    """Manufacturers currently being scraped."""
    db = get_db()
    rows = db.execute(
        """SELECT slug, display_name, scrape_status
           FROM manufacturers
           WHERE scrape_status = 'in_progress'
           ORDER BY display_name"""
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


@router.post("/trigger")
def trigger_scrape(payload: dict):
    """Trigger a scrape run. Payload: {slug: ...} or {wave: wave_1}."""
    slug = payload.get("slug")
    wave = payload.get("wave")
    if not slug and not wave:
        raise HTTPException(status_code=400, detail="Provide 'slug' or 'wave'")

    args = [sys.executable, str(SCRAPER_SCRIPT)]
    if slug:
        args.extend(["--slug", slug])
    elif wave:
        args.extend(["--wave", wave])

    # Fire-and-forget
    subprocess.Popen(
        args,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return {"triggered": True, "target": slug or wave}
