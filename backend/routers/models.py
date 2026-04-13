"""Model and floorplan API routes."""

import json
from fastapi import APIRouter, Query

from backend.database import get_db

router = APIRouter(prefix="/api", tags=["models"])


@router.get("/models")
def list_models(
    make: str | None = Query(None),
    year: int | None = Query(None),
    rv_class: str | None = Query(None),
    rv_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    db = get_db()
    query = "SELECT * FROM models WHERE 1=1"
    count_query = "SELECT COUNT(*) FROM models WHERE 1=1"
    params = []

    if make:
        query += " AND manufacturer_slug = ?"
        count_query += " AND manufacturer_slug = ?"
        params.append(make)
    if year:
        query += " AND model_year = ?"
        count_query += " AND model_year = ?"
        params.append(year)
    if rv_class:
        query += " AND rv_class = ?"
        count_query += " AND rv_class = ?"
        params.append(rv_class)
    if rv_type:
        query += " AND rv_type = ?"
        count_query += " AND rv_type = ?"
        params.append(rv_type)

    total = db.execute(count_query, params).fetchone()[0]

    query += " ORDER BY manufacturer_slug, model_name LIMIT ? OFFSET ?"
    params.extend([page_size, (page - 1) * page_size])
    rows = db.execute(query, params).fetchall()
    db.close()

    return {
        "items": [_model_row(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/models/{model_id}")
def get_model(model_id: int):
    db = get_db()
    row = db.execute("SELECT * FROM models WHERE id = ?", (model_id,)).fetchone()
    if not row:
        db.close()
        return {"error": "Not found"}, 404

    floorplans = db.execute(
        "SELECT * FROM floorplans WHERE model_id = ? ORDER BY floorplan_code", (model_id,)
    ).fetchall()

    images = db.execute(
        "SELECT * FROM images WHERE model_id = ? ORDER BY image_type", (model_id,)
    ).fetchall()

    db.close()

    model = _model_row(row)
    model["floorplans"] = [_floorplan_row(f) for f in floorplans]
    model["images"] = [_image_row(i) for i in images]
    return model


@router.get("/floorplans")
def list_floorplans(model_id: int | None = Query(None), make: str | None = Query(None)):
    db = get_db()
    query = "SELECT * FROM floorplans WHERE 1=1"
    params = []

    if model_id:
        query += " AND model_id = ?"
        params.append(model_id)
    if make:
        query += " AND manufacturer_slug = ?"
        params.append(make)

    query += " ORDER BY manufacturer_slug, model_name, floorplan_code LIMIT 200"
    rows = db.execute(query, params).fetchall()
    db.close()
    return [_floorplan_row(r) for r in rows]


@router.get("/floorplans/{floorplan_id}")
def get_floorplan(floorplan_id: int):
    db = get_db()
    row = db.execute("SELECT * FROM floorplans WHERE id = ?", (floorplan_id,)).fetchone()
    if not row:
        db.close()
        return {"error": "Not found"}, 404

    images = db.execute(
        "SELECT * FROM images WHERE floorplan_id = ? ORDER BY image_type", (floorplan_id,)
    ).fetchall()

    db.close()
    fp = _floorplan_row(row)
    fp["images"] = [_image_row(i) for i in images]
    return fp


@router.get("/lookup")
def lookup(
    make: str = Query(...),
    model: str = Query(...),
    year: int | None = Query(None),
):
    """Quick lookup for inventory enrichment. Returns best match for make/model/year."""
    db = get_db()

    # Try exact match first
    query = """
        SELECT m.*, mfr.display_name as manufacturer_display
        FROM models m
        JOIN manufacturers mfr ON m.manufacturer_id = mfr.id
        WHERE mfr.slug = ? AND LOWER(m.model_name) = LOWER(?)
    """
    params = [make, model]
    if year:
        query += " AND m.model_year = ?"
        params.append(year)
    query += " LIMIT 1"

    row = db.execute(query, params).fetchone()

    if not row:
        # Try fuzzy match on manufacturer name
        query = """
            SELECT m.*, mfr.display_name as manufacturer_display
            FROM models m
            JOIN manufacturers mfr ON m.manufacturer_id = mfr.id
            WHERE (LOWER(mfr.name) LIKE ? OR LOWER(mfr.display_name) LIKE ?)
              AND LOWER(m.model_name) LIKE ?
        """
        make_like = f"%{make.lower()}%"
        model_like = f"%{model.lower()}%"
        params = [make_like, make_like, model_like]
        if year:
            query += " AND m.model_year = ?"
            params.append(year)
        query += " LIMIT 1"
        row = db.execute(query, params).fetchone()

    if not row:
        db.close()
        return {"match": None, "floorplans": []}

    model_data = _model_row(row)
    floorplans = db.execute(
        "SELECT * FROM floorplans WHERE model_id = ?", (row["id"],)
    ).fetchall()
    db.close()

    return {
        "match": model_data,
        "floorplans": [_floorplan_row(f) for f in floorplans],
    }


def _model_row(row) -> dict:
    return {
        "id": row["id"],
        "manufacturer_slug": row["manufacturer_slug"],
        "model_name": row["model_name"],
        "model_year": row["model_year"],
        "series": row["series"],
        "rv_class": row["rv_class"],
        "rv_type": row["rv_type"],
        "length_ft_min": row["length_ft_min"],
        "length_ft_max": row["length_ft_max"],
        "gvwr_lbs_min": row["gvwr_lbs_min"],
        "gvwr_lbs_max": row["gvwr_lbs_max"],
        "dry_weight_lbs_min": row["dry_weight_lbs_min"],
        "dry_weight_lbs_max": row["dry_weight_lbs_max"],
        "sleeping_capacity_min": row["sleeping_capacity_min"],
        "sleeping_capacity_max": row["sleeping_capacity_max"],
        "slideout_count_min": row["slideout_count_min"],
        "slideout_count_max": row["slideout_count_max"],
        "base_msrp_usd": row["base_msrp_usd"],
        "data_quality": row["data_quality"],
        "floorplan_names": json.loads(row["floorplan_names"]) if row["floorplan_names"] else [],
        "notable_features": json.loads(row["notable_features"]) if row["notable_features"] else [],
    }


def _floorplan_row(row) -> dict:
    return {
        "id": row["id"],
        "model_id": row["model_id"],
        "manufacturer_slug": row["manufacturer_slug"],
        "model_name": row["model_name"],
        "model_year": row["model_year"],
        "floorplan_code": row["floorplan_code"],
        "floorplan_type": row["floorplan_type"],
        "length_ft": row["length_ft"],
        "width_ft": row["width_ft"],
        "sleeping_capacity": row["sleeping_capacity"],
        "slideout_count": row["slideout_count"],
        "bed_types": json.loads(row["bed_types"]) if row["bed_types"] else [],
        "bathroom_count": row["bathroom_count"],
        "dry_weight_lbs": row["dry_weight_lbs"],
        "gvwr_lbs": row["gvwr_lbs"],
        "msrp_usd": row["msrp_usd"],
        "data_quality": row["data_quality"],
        "standard_features": json.loads(row["standard_features"]) if row["standard_features"] else [],
    }


def _image_row(row) -> dict:
    return {
        "id": row["id"],
        "model_id": row["model_id"],
        "floorplan_id": row["floorplan_id"],
        "image_type": row["image_type"],
        "source_url": row["source_url"],
        "gcs_url": row["gcs_url"],
    }
