"""Health and coverage stats for the dashboard."""

from fastapi import APIRouter

from backend.database import get_db

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
def overview():
    """Dashboard overview stats."""
    db = get_db()

    stats = {}

    # Totals
    stats["total_manufacturers"] = db.execute("SELECT COUNT(*) FROM manufacturers").fetchone()[0]
    stats["active_manufacturers"] = db.execute(
        "SELECT COUNT(*) FROM manufacturers WHERE COALESCE(defunct, 0) = 0"
    ).fetchone()[0]
    stats["defunct_manufacturers"] = db.execute(
        "SELECT COUNT(*) FROM manufacturers WHERE COALESCE(defunct, 0) = 1"
    ).fetchone()[0]
    stats["total_models"] = db.execute("SELECT COUNT(*) FROM models").fetchone()[0]
    stats["total_floorplans"] = db.execute("SELECT COUNT(*) FROM floorplans").fetchone()[0]
    stats["total_images"] = db.execute("SELECT COUNT(*) FROM images").fetchone()[0]

    # Defunct brand list (so the dashboard can surface what's been retired)
    stats["defunct_list"] = [
        {"slug": r["slug"], "name": r["name"], "website": r["website"], "notes": r["notes"]}
        for r in db.execute(
            "SELECT slug, name, website, notes FROM manufacturers "
            "WHERE COALESCE(defunct, 0) = 1 ORDER BY slug"
        )
    ]

    # By tier
    tiers = {}
    for row in db.execute(
        """SELECT tier, COUNT(*) as total,
                  SUM(CASE WHEN scrape_status = 'complete' THEN 1 ELSE 0 END) as complete,
                  SUM(CASE WHEN scrape_status = 'partial' THEN 1 ELSE 0 END) as partial,
                  SUM(CASE WHEN scrape_status = 'not_started' THEN 1 ELSE 0 END) as not_started,
                  SUM(model_count) as models,
                  SUM(floorplan_count) as floorplans
           FROM manufacturers GROUP BY tier ORDER BY tier"""
    ):
        tiers[row["tier"]] = {
            "total": row["total"],
            "complete": row["complete"],
            "partial": row["partial"],
            "not_started": row["not_started"],
            "models": row["models"],
            "floorplans": row["floorplans"],
        }
    stats["tiers"] = tiers

    # By parent company
    parents = []
    for row in db.execute(
        """SELECT parent_company, COUNT(*) as brands,
                  SUM(model_count) as models, SUM(floorplan_count) as floorplans,
                  SUM(CASE WHEN scrape_status = 'complete' THEN 1 ELSE 0 END) as complete
           FROM manufacturers GROUP BY parent_company ORDER BY brands DESC"""
    ):
        parents.append({
            "name": row["parent_company"],
            "brands": row["brands"],
            "models": row["models"],
            "floorplans": row["floorplans"],
            "brands_complete": row["complete"],
        })
    stats["parent_companies"] = parents

    # By RV class
    classes = []
    for row in db.execute(
        """SELECT rv_class, COUNT(*) as model_count,
                  (SELECT COUNT(*) FROM floorplans f
                   JOIN models m2 ON f.model_id = m2.id
                   WHERE m2.rv_class = models.rv_class) as floorplan_count
           FROM models WHERE rv_class IS NOT NULL
           GROUP BY rv_class ORDER BY model_count DESC"""
    ):
        classes.append({
            "rv_class": row["rv_class"],
            "models": row["model_count"],
            "floorplans": row["floorplan_count"],
        })
    stats["rv_classes"] = classes

    # Data quality
    quality = {}
    for row in db.execute(
        "SELECT data_quality, COUNT(*) FROM models GROUP BY data_quality"
    ):
        quality[row[0]] = row[1]
    stats["data_quality"] = quality

    # Scrape status summary
    scrape = {}
    for row in db.execute(
        "SELECT scrape_status, COUNT(*) FROM manufacturers GROUP BY scrape_status"
    ):
        scrape[row[0]] = row[1]
    stats["scrape_status"] = scrape

    # Field completeness (across all floorplans)
    fp_total = stats["total_floorplans"]
    if fp_total > 0:
        comp = db.execute("""
            SELECT
                SUM(CASE WHEN length_ft IS NOT NULL THEN 1 ELSE 0 END) as length,
                SUM(CASE WHEN sleeping_capacity IS NOT NULL THEN 1 ELSE 0 END) as sleeping,
                SUM(CASE WHEN slideout_count IS NOT NULL THEN 1 ELSE 0 END) as slides,
                SUM(CASE WHEN bed_types IS NOT NULL THEN 1 ELSE 0 END) as beds,
                SUM(CASE WHEN msrp_usd IS NOT NULL THEN 1 ELSE 0 END) as msrp,
                SUM(CASE WHEN dry_weight_lbs IS NOT NULL THEN 1 ELSE 0 END) as weight,
                SUM(CASE WHEN fresh_water_gal IS NOT NULL THEN 1 ELSE 0 END) as fresh_water,
                SUM(CASE WHEN bathroom_count IS NOT NULL THEN 1 ELSE 0 END) as bathroom
            FROM floorplans
        """).fetchone()
        stats["field_completeness"] = {
            "total_floorplans": fp_total,
            "length_ft": round(comp["length"] / fp_total * 100, 1),
            "sleeping_capacity": round(comp["sleeping"] / fp_total * 100, 1),
            "slideout_count": round(comp["slides"] / fp_total * 100, 1),
            "bed_types": round(comp["beds"] / fp_total * 100, 1),
            "msrp_usd": round(comp["msrp"] / fp_total * 100, 1),
            "dry_weight_lbs": round(comp["weight"] / fp_total * 100, 1),
            "fresh_water_gal": round(comp["fresh_water"] / fp_total * 100, 1),
            "bathroom_count": round(comp["bathroom"] / fp_total * 100, 1),
        }
    else:
        stats["field_completeness"] = {}

    db.close()
    return stats


@router.get("/manufacturer/{slug}")
def manufacturer_health(slug: str):
    """Per-manufacturer completeness report."""
    db = get_db()

    mfr = db.execute("SELECT * FROM manufacturers WHERE slug = ?", (slug,)).fetchone()
    if not mfr:
        db.close()
        return {"error": "Not found"}, 404

    models = db.execute(
        "SELECT * FROM models WHERE manufacturer_slug = ?", (slug,)
    ).fetchall()

    model_ids = [m["id"] for m in models]
    fp_count = 0
    img_count = 0
    if model_ids:
        placeholders = ",".join("?" * len(model_ids))
        fp_count = db.execute(
            f"SELECT COUNT(*) FROM floorplans WHERE model_id IN ({placeholders})", model_ids
        ).fetchone()[0]
        img_count = db.execute(
            f"SELECT COUNT(*) FROM images WHERE model_id IN ({placeholders})", model_ids
        ).fetchone()[0]

    # Per-model breakdown
    model_details = []
    for m in models:
        fps = db.execute(
            "SELECT COUNT(*) FROM floorplans WHERE model_id = ?", (m["id"],)
        ).fetchone()[0]
        imgs = db.execute(
            "SELECT COUNT(*) FROM images WHERE model_id = ?", (m["id"],)
        ).fetchone()[0]
        model_details.append({
            "id": m["id"],
            "model_name": m["model_name"],
            "model_year": m["model_year"],
            "rv_class": m["rv_class"],
            "data_quality": m["data_quality"],
            "floorplan_count": fps,
            "image_count": imgs,
            "has_msrp": m["base_msrp_usd"] is not None,
        })

    # Scrape history
    runs = db.execute(
        """SELECT * FROM scrape_runs WHERE manufacturer_slug = ?
           ORDER BY started_at DESC LIMIT 10""",
        (slug,),
    ).fetchall()

    db.close()

    return {
        "manufacturer": {
            "slug": mfr["slug"],
            "name": mfr["name"],
            "display_name": mfr["display_name"],
            "parent_company": mfr["parent_company"],
            "tier": mfr["tier"],
            "scrape_status": mfr["scrape_status"],
            "last_scraped_at": mfr["last_scraped_at"],
        },
        "totals": {
            "models": len(models),
            "floorplans": fp_count,
            "images": img_count,
        },
        "models": model_details,
        "scrape_history": [dict(r) for r in runs],
    }
