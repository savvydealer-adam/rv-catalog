"""SQLite database connection and schema management."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "rv_catalog.db"


def get_db() -> sqlite3.Connection:
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def init_db():
    """Create all tables if they don't exist."""
    db = get_db()
    db.executescript(SCHEMA_SQL)
    db.commit()
    db.close()


SCHEMA_SQL = """
-- Parent companies (Thor Industries, Berkshire Hathaway, etc.)
CREATE TABLE IF NOT EXISTS parent_companies (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL UNIQUE,
    ticker            TEXT,
    market_share_pct  REAL,
    brand_count       INTEGER DEFAULT 0,
    website           TEXT,
    notes             TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now','utc')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now','utc'))
);

-- Manufacturers / brands
CREATE TABLE IF NOT EXISTS manufacturers (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    slug              TEXT NOT NULL UNIQUE,
    name              TEXT NOT NULL UNIQUE,
    display_name      TEXT NOT NULL,
    parent_company_id INTEGER REFERENCES parent_companies(id),
    parent_company    TEXT,
    headquarters      TEXT,
    website           TEXT,
    rv_types          TEXT,       -- JSON array: ["motorized","towable"]
    tier              TEXT NOT NULL DEFAULT 'wave_4',  -- wave_1, wave_2, wave_3, wave_4
    scrape_priority   INTEGER NOT NULL DEFAULT 99,
    scrape_status     TEXT NOT NULL DEFAULT 'not_started',  -- not_started, in_progress, partial, complete
    last_scraped_at   TEXT,
    model_count       INTEGER DEFAULT 0,
    floorplan_count   INTEGER DEFAULT 0,
    image_count       INTEGER DEFAULT 0,
    coverage_pct      REAL DEFAULT 0.0,
    rvia_member       INTEGER DEFAULT 1,
    notes             TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now','utc')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now','utc'))
);

-- Models (series/product lines)
CREATE TABLE IF NOT EXISTS models (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    manufacturer_id      INTEGER NOT NULL REFERENCES manufacturers(id) ON DELETE CASCADE,
    manufacturer_slug    TEXT NOT NULL,
    model_year           INTEGER,
    model_name           TEXT NOT NULL,
    series               TEXT,
    rv_class             TEXT,       -- "Class A", "Class B", "Class C", "Fifth Wheel", "Travel Trailer", "Toy Hauler", "Truck Camper", "Pop-Up", "Park Model"
    rv_type              TEXT,       -- "motorized" | "towable"
    length_ft_min        REAL,
    length_ft_max        REAL,
    width_ft             REAL,
    gvwr_lbs_min         INTEGER,
    gvwr_lbs_max         INTEGER,
    dry_weight_lbs_min   INTEGER,
    dry_weight_lbs_max   INTEGER,
    hitch_weight_lbs     INTEGER,
    sleeping_capacity_min INTEGER,
    sleeping_capacity_max INTEGER,
    slideout_count_min   INTEGER,
    slideout_count_max   INTEGER,
    bathroom_count_min   INTEGER,
    bathroom_count_max   INTEGER,
    base_msrp_usd        INTEGER,
    chassis              TEXT,
    engine               TEXT,
    fuel_type            TEXT,
    shore_power_amps     TEXT,
    fresh_water_gal      REAL,
    gray_water_gal       REAL,
    black_water_gal      REAL,
    propane_tanks         INTEGER,
    ac_units              INTEGER,
    awning_length_ft     REAL,
    floorplan_names      TEXT,       -- JSON array of floorplan codes
    notable_features     TEXT,       -- JSON array
    source_url           TEXT,
    data_quality         TEXT NOT NULL DEFAULT 'pending',  -- "scraped", "ai_generated", "manual", "pending"
    created_at           TEXT NOT NULL DEFAULT (datetime('now','utc')),
    updated_at           TEXT NOT NULL DEFAULT (datetime('now','utc')),
    UNIQUE(manufacturer_slug, model_name, model_year)
);

-- Floorplans (individual layouts within a model)
CREATE TABLE IF NOT EXISTS floorplans (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id            INTEGER NOT NULL REFERENCES models(id) ON DELETE CASCADE,
    manufacturer_slug   TEXT NOT NULL,
    model_name          TEXT NOT NULL,
    model_year          INTEGER,
    floorplan_code      TEXT NOT NULL,
    floorplan_type      TEXT,
    length_ft           REAL,
    width_ft            REAL,
    interior_height_ft  REAL,
    ext_height_ft       REAL,
    sleeping_capacity   INTEGER,
    slideout_count      INTEGER,
    bed_types           TEXT,           -- JSON array
    bathroom_count      INTEGER,
    half_bath           INTEGER DEFAULT 0,
    dry_weight_lbs      INTEGER,
    gvwr_lbs            INTEGER,
    hitch_weight_lbs    INTEGER,
    cargo_capacity_lbs  INTEGER,
    fresh_water_gal     REAL,
    gray_water_gal      REAL,
    black_water_gal     REAL,
    msrp_usd            INTEGER,
    standard_features   TEXT,           -- JSON array
    source_url          TEXT,
    data_quality        TEXT NOT NULL DEFAULT 'pending',
    created_at          TEXT NOT NULL DEFAULT (datetime('now','utc')),
    UNIQUE(model_id, floorplan_code)
);

-- Images
CREATE TABLE IF NOT EXISTS images (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id        INTEGER REFERENCES models(id) ON DELETE CASCADE,
    floorplan_id    INTEGER REFERENCES floorplans(id) ON DELETE CASCADE,
    manufacturer_slug TEXT NOT NULL,
    model_name      TEXT,
    image_type      TEXT NOT NULL,  -- "floorplan", "exterior", "interior", "hero", "brochure"
    local_path      TEXT,
    source_url      TEXT,
    gcs_url         TEXT,
    width_px        INTEGER,
    height_px       INTEGER,
    file_size_bytes INTEGER,
    created_at      TEXT NOT NULL DEFAULT (datetime('now','utc')),
    -- Allow the same image URL to be associated with multiple models
    -- (e.g. floorplan images shared between a parent series and its sub-models).
    UNIQUE(model_id, source_url)
);

-- Scrape run tracking
CREATE TABLE IF NOT EXISTS scrape_runs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    manufacturer_id   INTEGER NOT NULL REFERENCES manufacturers(id),
    manufacturer_slug TEXT NOT NULL,
    started_at        TEXT NOT NULL DEFAULT (datetime('now','utc')),
    finished_at       TEXT,
    status            TEXT NOT NULL DEFAULT 'running',  -- running, success, partial, error
    models_found      INTEGER DEFAULT 0,
    models_added      INTEGER DEFAULT 0,
    floorplans_found  INTEGER DEFAULT 0,
    floorplans_added  INTEGER DEFAULT 0,
    images_downloaded INTEGER DEFAULT 0,
    errors            TEXT,           -- JSON array of error messages
    duration_s        REAL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_models_manufacturer ON models(manufacturer_id);
CREATE INDEX IF NOT EXISTS idx_models_slug ON models(manufacturer_slug);
CREATE INDEX IF NOT EXISTS idx_models_class ON models(rv_class);
CREATE INDEX IF NOT EXISTS idx_models_year ON models(model_year);
CREATE INDEX IF NOT EXISTS idx_floorplans_model ON floorplans(model_id);
CREATE INDEX IF NOT EXISTS idx_images_model ON images(model_id);
CREATE INDEX IF NOT EXISTS idx_images_floorplan ON images(floorplan_id);
CREATE INDEX IF NOT EXISTS idx_manufacturers_tier ON manufacturers(tier);
CREATE INDEX IF NOT EXISTS idx_manufacturers_status ON manufacturers(scrape_status);
"""
