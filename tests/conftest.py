"""Shared fixtures for the API smoke suite.

The suite is hermetic: it builds a temporary SQLite DB with the real schema
and a small seed, then points ``backend.database.DB_PATH`` at it. The real
``data/rv_catalog.db`` (gitignored) is never touched, and the tests pass on a
fresh clone where the DB does not exist yet.
"""

import os
import sqlite3
import sys
from pathlib import Path

import pytest

# Must be set before importing backend.auth (SKIP_AUTH is frozen at import time).
os.environ["ENVIRONMENT"] = "development"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import backend.database as database  # noqa: E402


SEED_SQL = """
INSERT INTO parent_companies (name, ticker) VALUES ('Thor Industries', 'THO');

INSERT INTO manufacturers
  (slug, name, display_name, parent_company, tier, scrape_priority, scrape_status,
   model_count, floorplan_count, image_count, defunct)
VALUES
  ('jayco', 'Jayco', 'Jayco', 'Thor Industries', 'wave_1', 1, 'complete', 2, 1, 2, 0),
  ('old-brand', 'Old Brand', 'Old Brand', NULL, 'wave_4', 99, 'defunct', 0, 0, 0, 1);

INSERT INTO models
  (manufacturer_id, manufacturer_slug, model_year, model_name, series, rv_class, rv_type,
   base_msrp_usd, floorplan_names, data_quality)
VALUES
  (1, 'jayco', 2024, 'Grey Wolf', 'Grey Wolf', 'Fifth Wheel', 'towable', 62000,
   '["37FRZ","41FWS"]', 'scraped'),
  (1, 'jayco', 2025, 'Redhawk', 'Redhawk', 'Class C', 'motorized', 91000, NULL,
   'scraped');

INSERT INTO floorplans
  (model_id, manufacturer_slug, model_name, model_year, floorplan_code, floorplan_type,
   length_ft, sleeping_capacity, msrp_usd, data_quality)
VALUES
  (1, 'jayco', 'Grey Wolf', 2024, '37FRZ', 'rear_kitchen', 37.0, 6, 64500, 'scraped');

INSERT INTO images
  (model_id, floorplan_id, manufacturer_slug, model_name, image_type, source_url)
VALUES
  (1, 1, 'jayco', 'Grey Wolf', 'floorplan', 'https://example.com/floorplans/37FRZ.png'),
  (1, NULL, 'jayco', 'Grey Wolf', 'exterior', 'https://example.com/exteriors/greywolf.jpg');

INSERT INTO scrape_runs
  (manufacturer_id, manufacturer_slug, status, models_found, models_added,
   floorplans_found, floorplans_added, duration_s)
VALUES
  (1, 'jayco', 'success', 2, 2, 1, 1, 12.5);
"""


@pytest.fixture(scope="session")
def db_path(tmp_path_factory) -> Path:
    """Temporary SQLite DB with the real schema plus seed rows."""
    path = tmp_path_factory.mktemp("db") / "rv_catalog_test.db"
    db = sqlite3.connect(str(path))
    db.executescript(database.SCHEMA_SQL)
    db.executescript(SEED_SQL)
    db.commit()
    db.close()
    return path


@pytest.fixture(scope="session")
def client(db_path, monkeypatch_session):
    monkeypatch_session.setattr(database, "DB_PATH", db_path)
    from fastapi.testclient import TestClient

    import backend.main

    with TestClient(backend.main.app) as c:
        yield c


@pytest.fixture(scope="session")
def monkeypatch_session():
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    yield mp
    mp.undo()
