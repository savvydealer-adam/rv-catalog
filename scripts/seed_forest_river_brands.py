"""Seed Forest River's major sub-brands as separate manufacturer entries.

Forest River operates 30+ semi-autonomous divisions, each with distinct
product lines. For accurate catalog coverage, each major brand needs its
own scrape entry.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.database import get_db, init_db


# Major Forest River sub-brands with their own domains/product pages
# (slug, name, display_name, website, rv_types, tier, priority)
FR_BRANDS = [
    # Top Forest River sub-brands (by volume)
    ("cherokee-rv", "Cherokee RV", "Cherokee", "https://cherokeerv.com", ["towable"], "wave_1", 70),
    ("salem-rv", "Salem RV", "Salem", "https://forestriverinc.com/rvs/travel-trailers/salem", ["towable"], "wave_1", 71),
    ("wildwood-rv", "Wildwood RV", "Wildwood", "https://forestriverinc.com/rvs/travel-trailers/wildwood", ["towable"], "wave_1", 72),
    ("rockwood", "Rockwood RV", "Rockwood", "https://forestriverinc.com/rvs/travel-trailers/rockwood", ["towable"], "wave_2", 73),
    ("flagstaff-rv", "Flagstaff RV", "Flagstaff", "https://forestriverinc.com/rvs/travel-trailers/flagstaff", ["towable"], "wave_2", 74),
    ("sabre", "Sabre", "Sabre", "https://forestriverinc.com/rvs/fifth-wheels/sabre", ["towable"], "wave_2", 75),
    ("sandpiper", "Sandpiper", "Sandpiper", "https://forestriverinc.com/rvs/fifth-wheels/sandpiper", ["towable"], "wave_2", 76),
    ("cedar-creek", "Cedar Creek", "Cedar Creek", "https://forestriverinc.com/rvs/fifth-wheels/cedar-creek", ["towable"], "wave_3", 77),
    ("sierra", "Sierra", "Sierra", "https://forestriverinc.com/rvs/fifth-wheels/sierra", ["towable"], "wave_3", 78),
    ("cardinal", "Cardinal", "Cardinal", "https://forestriverinc.com/rvs/fifth-wheels/cardinal", ["towable"], "wave_3", 79),
    ("r-pod", "R-Pod", "R-Pod", "https://forestriverinc.com/rvs/travel-trailers/r-pod", ["towable"], "wave_3", 80),
    ("ibex", "IBEX", "IBEX", "https://forestriverinc.com/rvs/travel-trailers/ibex", ["towable"], "wave_3", 81),
    ("surveyor", "Surveyor", "Surveyor", "https://forestriverinc.com/rvs/travel-trailers/surveyor", ["towable"], "wave_3", 82),
    ("vibe-rv", "Vibe", "Vibe", "https://forestriverinc.com/rvs/travel-trailers/vibe", ["towable"], "wave_3", 83),
    ("riverstone", "Riverstone", "Riverstone", "https://forestriverinc.com/rvs/fifth-wheels/riverstone", ["towable"], "wave_3", 84),
    ("sunseeker", "Sunseeker", "Sunseeker", "https://forestriverinc.com/rvs/motorhomes/sunseeker", ["motorized"], "wave_2", 85),
    ("forester", "Forester MBS", "Forester", "https://forestriverinc.com/rvs/motorhomes/forester", ["motorized"], "wave_3", 86),
    ("georgetown", "Georgetown", "Georgetown", "https://forestriverinc.com/rvs/motorhomes/georgetown", ["motorized"], "wave_3", 87),
    ("solera", "Solera", "Solera", "https://forestriverinc.com/rvs/motorhomes/solera", ["motorized"], "wave_3", 88),
    ("fr3", "FR3", "FR3", "https://forestriverinc.com/rvs/motorhomes/fr3", ["motorized"], "wave_3", 89),
    ("xlr-toy-hauler", "XLR", "XLR", "https://forestriverinc.com/rvs/toy-haulers/xlr", ["towable"], "wave_3", 90),
    ("cherokee-arctic-wolf", "Cherokee Arctic Wolf", "Arctic Wolf", "https://cherokeerv.com/arctic-wolf", ["towable"], "wave_2", 91),
    ("cherokee-grey-wolf", "Cherokee Grey Wolf", "Grey Wolf", "https://cherokeerv.com/grey-wolf", ["towable"], "wave_2", 92),
    ("cherokee-wolf-pup", "Cherokee Wolf Pup", "Wolf Pup", "https://cherokeerv.com/wolf-pup", ["towable"], "wave_3", 93),
    ("no-boundaries", "No Boundaries", "No Boundaries", "https://forestriverinc.com/rvs/travel-trailers/no-boundaries", ["towable"], "wave_3", 94),
    ("work-and-play", "Work and Play", "Work and Play", "https://forestriverinc.com/rvs/toy-haulers/work-and-play", ["towable"], "wave_4", 95),
    ("stealth", "Stealth", "Stealth", "https://forestriverinc.com/rvs/toy-haulers/stealth", ["towable"], "wave_4", 96),
    ("vengeance", "Vengeance", "Vengeance", "https://forestriverinc.com/rvs/toy-haulers/vengeance", ["towable"], "wave_4", 97),
]

FR_PARENT = "Forest River (Berkshire Hathaway)"


def seed():
    init_db()
    db = get_db()

    pc = db.execute(
        "SELECT id FROM parent_companies WHERE name = ?", (FR_PARENT,)
    ).fetchone()
    pc_id = pc["id"] if pc else None

    inserted = 0
    updated = 0
    for slug, name, display, website, rv_types, tier, priority in FR_BRANDS:
        try:
            db.execute(
                """INSERT INTO manufacturers
                   (slug, name, display_name, parent_company_id, parent_company,
                    website, rv_types, tier, scrape_priority)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (slug, name, display, pc_id, FR_PARENT, website,
                 json.dumps(rv_types), tier, priority),
            )
            inserted += 1
        except Exception as e:
            if "UNIQUE" in str(e):
                db.execute(
                    """UPDATE manufacturers SET
                       display_name=?, parent_company_id=?, parent_company=?,
                       website=?, rv_types=?, tier=?, scrape_priority=?
                       WHERE slug=?""",
                    (display, pc_id, FR_PARENT, website, json.dumps(rv_types), tier, priority, slug),
                )
                updated += 1
            else:
                raise

    db.commit()

    # Update parent company brand count
    db.execute("""
        UPDATE parent_companies SET brand_count = (
            SELECT COUNT(*) FROM manufacturers WHERE parent_company_id = parent_companies.id
        )
    """)
    db.commit()

    total = db.execute("SELECT COUNT(*) FROM manufacturers").fetchone()[0]
    print(f"Seeded {inserted} new FR sub-brands, updated {updated}. Total manufacturers: {total}")
    db.close()


if __name__ == "__main__":
    seed()
