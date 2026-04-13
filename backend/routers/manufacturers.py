"""Manufacturer API routes."""

import json
from fastapi import APIRouter, Query

from backend.database import get_db

router = APIRouter(prefix="/api/manufacturers", tags=["manufacturers"])


@router.get("")
def list_manufacturers(
    tier: str | None = Query(None, description="Filter by tier: wave_1, wave_2, wave_3, wave_4"),
    parent: str | None = Query(None, description="Filter by parent company name"),
    status: str | None = Query(None, description="Filter by scrape_status"),
):
    db = get_db()
    query = "SELECT * FROM manufacturers WHERE 1=1"
    params = []

    if tier:
        query += " AND tier = ?"
        params.append(tier)
    if parent:
        query += " AND parent_company LIKE ?"
        params.append(f"%{parent}%")
    if status:
        query += " AND scrape_status = ?"
        params.append(status)

    query += " ORDER BY scrape_priority ASC"
    rows = db.execute(query, params).fetchall()
    db.close()

    return [_mfr_row(r) for r in rows]


@router.get("/{slug}")
def get_manufacturer(slug: str):
    db = get_db()
    row = db.execute("SELECT * FROM manufacturers WHERE slug = ?", (slug,)).fetchone()
    if not row:
        db.close()
        return {"error": "Not found"}, 404

    # Get models for this manufacturer
    models = db.execute(
        """SELECT id, model_name, model_year, rv_class, rv_type, data_quality,
                  (SELECT COUNT(*) FROM floorplans WHERE model_id = models.id) as floorplan_count
           FROM models WHERE manufacturer_slug = ? ORDER BY model_name""",
        (slug,),
    ).fetchall()

    db.close()

    mfr = _mfr_row(row)
    mfr["models"] = [
        {
            "id": m["id"],
            "model_name": m["model_name"],
            "model_year": m["model_year"],
            "rv_class": m["rv_class"],
            "rv_type": m["rv_type"],
            "data_quality": m["data_quality"],
            "floorplan_count": m["floorplan_count"],
        }
        for m in models
    ]
    return mfr


def _mfr_row(row) -> dict:
    return {
        "id": row["id"],
        "slug": row["slug"],
        "name": row["name"],
        "display_name": row["display_name"],
        "parent_company": row["parent_company"],
        "website": row["website"],
        "rv_types": json.loads(row["rv_types"]) if row["rv_types"] else [],
        "tier": row["tier"],
        "scrape_priority": row["scrape_priority"],
        "scrape_status": row["scrape_status"],
        "last_scraped_at": row["last_scraped_at"],
        "model_count": row["model_count"],
        "floorplan_count": row["floorplan_count"],
        "image_count": row["image_count"],
        "coverage_pct": row["coverage_pct"],
    }
