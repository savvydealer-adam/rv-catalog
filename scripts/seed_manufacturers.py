"""Seed all 65+ RV manufacturers with priority tiers and parent companies."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.database import get_db, init_db


PARENT_COMPANIES = [
    {"name": "Thor Industries", "ticker": "THO", "market_share_pct": 41.0, "website": "https://thorindustries.com"},
    {"name": "Forest River (Berkshire Hathaway)", "ticker": "BRK.B", "market_share_pct": 36.0, "website": "https://forestriverinc.com"},
    {"name": "Winnebago Industries", "ticker": "WGO", "market_share_pct": 11.0, "website": "https://winnebagoind.com"},
    {"name": "REV Group", "ticker": "REVG", "market_share_pct": 3.5, "website": "https://revgroup.com"},
    {"name": "Independent", "ticker": None, "market_share_pct": 8.5, "website": None},
]


# (slug, name, display_name, parent_company, website, rv_types, tier, priority)
MANUFACTURERS = [
    # === WAVE 1: Big 8 Flagships (~70% market) ===
    ("keystone", "Keystone RV", "Keystone", "Thor Industries", "https://keystonerv.com", ["towable"], "wave_1", 1),
    ("forest-river", "Forest River", "Forest River", "Forest River (Berkshire Hathaway)", "https://forestriverinc.com", ["motorized", "towable"], "wave_1", 2),
    ("jayco", "Jayco", "Jayco", "Thor Industries", "https://jayco.com", ["motorized", "towable"], "wave_1", 3),
    ("grand-design", "Grand Design RV", "Grand Design", "Winnebago Industries", "https://granddesignrv.com", ["towable"], "wave_1", 4),
    ("heartland", "Heartland RV", "Heartland", "Thor Industries", "https://heartlandrvs.com", ["towable"], "wave_1", 5),
    ("coachmen", "Coachmen RV", "Coachmen", "Forest River (Berkshire Hathaway)", "https://coachmenrv.com", ["motorized", "towable"], "wave_1", 6),
    ("winnebago", "Winnebago", "Winnebago", "Winnebago Industries", "https://winnebago.com", ["motorized", "towable"], "wave_1", 7),
    ("thor-motor-coach", "Thor Motor Coach", "Thor Motor Coach", "Thor Industries", "https://thormotorcoach.com", ["motorized"], "wave_1", 8),

    # === WAVE 2: Major Secondary Brands (~15% additional) ===
    ("dutchmen", "Dutchmen", "Dutchmen", "Thor Industries", "https://dutchmen.com", ["towable"], "wave_2", 9),
    ("prime-time", "Prime Time Manufacturing", "Prime Time", "Forest River (Berkshire Hathaway)", "https://primetimerv.com", ["towable"], "wave_2", 10),
    ("palomino", "Palomino RV", "Palomino", "Forest River (Berkshire Hathaway)", "https://palominorv.com", ["towable"], "wave_2", 11),
    ("kz", "KZ RV", "KZ", "Thor Industries", "https://kz-rv.com", ["towable"], "wave_2", 12),
    ("airstream", "Airstream", "Airstream", "Thor Industries", "https://airstream.com", ["motorized", "towable"], "wave_2", 13),
    ("highland-ridge", "Highland Ridge RV", "Highland Ridge", "Thor Industries", "https://highlandridgerv.com", ["towable"], "wave_2", 14),
    ("fleetwood", "Fleetwood RV", "Fleetwood", "REV Group", "https://fleetwoodrv.com", ["motorized"], "wave_2", 15),
    ("holiday-rambler", "Holiday Rambler", "Holiday Rambler", "REV Group", "https://holidayrambler.com", ["motorized"], "wave_2", 16),
    ("gulf-stream", "Gulf Stream Coach", "Gulf Stream", "Independent", "https://gulfstreamcoach.com", ["motorized", "towable"], "wave_2", 17),

    # === WAVE 3: Mid-Tier & Growing Brands ===
    ("shasta", "Shasta RV", "Shasta", "Forest River (Berkshire Hathaway)", "https://shastarving.com", ["towable"], "wave_3", 18),
    ("east-to-west", "East to West RV", "East to West", "Forest River (Berkshire Hathaway)", "https://easttowestrv.com", ["towable"], "wave_3", 19),
    ("starcraft", "Starcraft RV", "Starcraft", "Thor Industries", "https://starcraftrv.com", ["towable"], "wave_3", 20),
    ("entegra", "Entegra Coach", "Entegra Coach", "Thor Industries", "https://entegracoach.com", ["motorized"], "wave_3", 21),
    ("tiffin", "Tiffin Motorhomes", "Tiffin", "Thor Industries", "https://tiffinmotorhomes.com", ["motorized"], "wave_3", 22),
    ("newmar", "Newmar Corporation", "Newmar", "Winnebago Industries", "https://newmarcorp.com", ["motorized"], "wave_3", 23),
    ("crossroads", "Crossroads RV", "Crossroads", "Thor Industries", "https://crossroadsrv.com", ["towable"], "wave_3", 24),
    ("alliance", "Alliance RV", "Alliance", "Independent", "https://alliancerv.com", ["towable"], "wave_3", 25),
    ("brinkley", "Brinkley RV", "Brinkley", "Independent", "https://brinkleyrv.com", ["towable"], "wave_3", 26),
    ("dynamax", "Dynamax Corporation", "Dynamax", "Forest River (Berkshire Hathaway)", "https://dynamaxcorp.com", ["motorized"], "wave_3", 27),
    ("lance", "Lance Camper", "Lance", "Independent", "https://lancecamper.com", ["towable"], "wave_3", 28),

    # === WAVE 4: Long Tail Independents & Specialty ===
    ("northwood", "Northwood Manufacturing", "Northwood", "Independent", "https://northwoodmfg.com", ["towable"], "wave_4", 29),
    ("ember", "Ember RV", "Ember", "Independent", "https://emberrv.com", ["towable"], "wave_4", 30),
    ("intech", "inTech RV", "inTech", "Independent", "https://intechrv.com", ["towable"], "wave_4", 31),
    ("nucamp", "nuCamp RV", "nuCamp", "Independent", "https://nucamprv.com", ["towable"], "wave_4", 32),
    ("outdoors-rv", "Outdoors RV", "Outdoors RV", "Independent", "https://outdoorsrvmfg.com", ["towable"], "wave_4", 33),
    ("pleasure-way", "Pleasure-Way Industries", "Pleasure-Way", "Independent", "https://pleasureway.com", ["motorized"], "wave_4", 34),
    ("leisure-travel", "Leisure Travel Vans", "Leisure Travel Vans", "Independent", "https://leisurevans.com", ["motorized"], "wave_4", 35),
    ("cruiser-rv", "Cruiser RV", "Cruiser RV", "Thor Industries", "https://cruiserrv.com", ["towable"], "wave_4", 36),
    ("drv", "DRV Luxury Suites", "DRV", "Thor Industries", "https://drvsuites.com", ["towable"], "wave_4", 37),
    ("venture", "Venture RV", "Venture RV", "Thor Industries", "https://venture-rv.com", ["towable"], "wave_4", 38),
    ("oliver", "Oliver Travel Trailers", "Oliver", "Independent", "https://olivertraveltrailers.com", ["towable"], "wave_4", 39),
    ("travel-lite", "Travel Lite RV", "Travel Lite", "Independent", "https://travelliterv.com", ["towable"], "wave_4", 40),
    ("coach-house", "Coach House RV", "Coach House", "Independent", "https://coachhouserv.com", ["motorized"], "wave_4", 41),
    ("roadtrek", "Roadtrek", "Roadtrek", "Independent", "https://roadtrek.com", ["motorized"], "wave_4", 42),
    ("american-coach", "American Coach", "American Coach", "REV Group", "https://americancoach.com", ["motorized"], "wave_4", 43),
    ("renegade", "Renegade RV", "Renegade", "REV Group", "https://raborv.com", ["motorized"], "wave_4", 44),
    ("midwest-auto", "Midwest Automotive Designs", "Midwest", "REV Group", "https://midwestautomotivedesigns.com", ["motorized"], "wave_4", 45),
    ("aliner", "Aliner", "Aliner", "Independent", "https://aliner.com", ["towable"], "wave_4", 46),
    ("scamp", "Scamp Trailers", "Scamp", "Independent", "https://scamptrailers.com", ["towable"], "wave_4", 47),
    ("casita", "Casita Travel Trailers", "Casita", "Independent", "https://casitatraveltrailers.com", ["towable"], "wave_4", 48),
    ("bowlus", "Bowlus", "Bowlus", "Independent", "https://bowlus.com", ["towable"], "wave_4", 49),
    ("northern-lite", "Northern Lite", "Northern Lite", "Independent", "https://northern-lite.com", ["towable"], "wave_4", 50),
    ("northstar", "Northstar Campers", "Northstar", "Independent", "https://northstarcampers.com", ["towable"], "wave_4", 51),
    ("bigfoot", "Bigfoot Industries", "Bigfoot", "Independent", "https://bigfootrv.com", ["towable"], "wave_4", 52),
    ("host", "Host Campers", "Host", "Independent", "https://hostcampers.com", ["towable"], "wave_4", 53),
    ("earthroamer", "EarthRoamer", "EarthRoamer", "Independent", "https://earthroamer.com", ["motorized"], "wave_4", 54),
    ("hiker", "Hiker Trailers", "Hiker", "Independent", "https://hikertrailers.com", ["towable"], "wave_4", 55),
    ("storyteller", "Storyteller Overland", "Storyteller", "Independent", "https://storytelleroverland.com", ["motorized"], "wave_4", 56),
    ("redwood", "Redwood RV", "Redwood", "Thor Industries", "https://redwood-rv.com", ["towable"], "wave_4", 57),
    ("genesis-supreme", "Genesis Supreme RV", "Genesis Supreme", "Independent", "https://genesissupreme.com", ["towable"], "wave_4", 58),
    ("sunset-park", "Sunset Park RV", "Sunset Park", "Independent", "https://sunsetparkrv.com", ["towable"], "wave_4", 59),
    ("braxton-creek", "Braxton Creek", "Braxton Creek", "Independent", "https://braxtoncreek.com", ["towable"], "wave_4", 60),
    ("taxa", "Taxa Outdoors", "Taxa", "Independent", "https://taxaoutdoors.com", ["towable"], "wave_4", 61),
    ("happier-camper", "Happier Camper", "Happier Camper", "Independent", "https://happiercamper.com", ["towable"], "wave_4", 62),
    ("adventurer", "Adventurer Manufacturing", "Adventurer", "Independent", "https://adventurermfg.com", ["towable"], "wave_4", 63),
    ("regency", "Regency RV", "Regency", "Independent", "https://regencyrv.com", ["motorized"], "wave_4", 64),
    ("encore", "Encore RV", "Encore", "Independent", "https://encorerv.com", ["towable"], "wave_4", 65),
]


def seed():
    init_db()
    db = get_db()

    # Seed parent companies
    for pc in PARENT_COMPANIES:
        db.execute(
            """INSERT OR IGNORE INTO parent_companies (name, ticker, market_share_pct, website)
               VALUES (?, ?, ?, ?)""",
            (pc["name"], pc["ticker"], pc["market_share_pct"], pc["website"]),
        )
    db.commit()

    # Get parent company IDs
    pc_map = {}
    for row in db.execute("SELECT id, name FROM parent_companies"):
        pc_map[row["name"]] = row["id"]

    # Seed manufacturers
    inserted = 0
    for slug, name, display, parent, website, rv_types, tier, priority in MANUFACTURERS:
        parent_id = pc_map.get(parent)
        try:
            db.execute(
                """INSERT INTO manufacturers
                   (slug, name, display_name, parent_company_id, parent_company,
                    website, rv_types, tier, scrape_priority)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (slug, name, display, parent_id, parent, website, json.dumps(rv_types), tier, priority),
            )
            inserted += 1
        except Exception as e:
            if "UNIQUE" in str(e):
                # Update existing
                db.execute(
                    """UPDATE manufacturers SET
                       display_name=?, parent_company_id=?, parent_company=?,
                       website=?, rv_types=?, tier=?, scrape_priority=?
                       WHERE slug=?""",
                    (display, parent_id, parent, website, json.dumps(rv_types), tier, priority, slug),
                )
            else:
                raise

    db.commit()

    # Update parent company brand counts
    db.execute("""
        UPDATE parent_companies SET brand_count = (
            SELECT COUNT(*) FROM manufacturers WHERE parent_company_id = parent_companies.id
        )
    """)
    db.commit()

    # Report
    total = db.execute("SELECT COUNT(*) FROM manufacturers").fetchone()[0]
    parents = db.execute("SELECT COUNT(*) FROM parent_companies").fetchone()[0]
    print(f"Seeded {inserted} manufacturers ({total} total), {parents} parent companies")

    for tier_name in ["wave_1", "wave_2", "wave_3", "wave_4"]:
        count = db.execute("SELECT COUNT(*) FROM manufacturers WHERE tier=?", (tier_name,)).fetchone()[0]
        print(f"  {tier_name}: {count} brands")

    db.close()


if __name__ == "__main__":
    seed()
