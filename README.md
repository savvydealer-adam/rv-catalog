# RV Catalog

Central RV knowledge base. Owns manufacturer, model, floorplan, and image data
for every active RV OEM. Dealer websites call this API instead of maintaining
their own knowledge bases.

**Coverage (2026-05-11):** 93 manufacturers, 83 active, 1,324 models,
3,650 floorplans, 18,484 images.

## Stack

- **Backend:** FastAPI on Python 3.12, SQLite (`data/rv_catalog.db`)
- **Frontend:** React + Vite admin dashboard (Google OAuth in prod)
- **Scrapers:** httpx + Playwright + puppeteer-real-browser (WAF bypass);
  Gemini 2.5 Flash for structured extraction
- **Deploy:** Cloud Run service `rv-catalog` in project `savvydealer-website`,
  region `us-central1`

## Quick start

```bash
# 1. Install Python deps
pip install -r requirements.txt   # if present; otherwise see Dockerfile

# 2. Build dashboard (optional, only if you want the UI at /)
cd dashboard && npm install && npm run build && cd ..

# 3. Run the backend
ENVIRONMENT=development python -m uvicorn backend.main:app --reload --port 8080

# 4. Hit the API
curl http://localhost:8080/api/health
curl http://localhost:8080/api/manufacturers
```

In `ENVIRONMENT=development` mode auth is stubbed and `/api-docs` is exposed.
In production a real Google ID token is required (configured via
`GOOGLE_CLIENT_ID` and `ALLOWED_DOMAIN`).

## API surface

See `PLAN.md` for the full list. Headline routes:

```
GET  /api/manufacturers
GET  /api/manufacturers/{slug}
GET  /api/models?make=&year=&class=
GET  /api/models/{model_id}              -> returns floorplans + images bundled
GET  /api/floorplans?model_id=
GET  /api/floorplans/{floorplan_id}
GET  /api/lookup?make=&model=&year=      -> for inventory enrichment
GET  /api/health                          -> coverage stats
POST /api/scrape/trigger                  -> body {slug:...} or {wave:...}
```

## Scraping

```bash
# Single brand
GEMINI_API_KEY=... python scripts/run_scraper.py --slug jayco

# A wave (per brand_configs.py)
GEMINI_API_KEY=... python scripts/run_scraper.py --wave wave_1

# Everything
GEMINI_API_KEY=... python scripts/run_scraper.py --all
```

The pipeline goes: `_discover_models` (listing pages, sitemap, brand_configs
seeds) → `_extract_model` (Gemini structured extraction) → `_persist` (SQLite
upsert keyed by `(model_id, source_url)` etc).

Hard sites are routed through Playwright (`force_playwright`) or stealth
(`force_stealth`, runs a real Chrome via puppeteer-real-browser locally — see
`scripts/stealth/`).

## STL RV sync

`scripts/sync_to_stl_rv.py` mirrors the catalog into STL RV's Supabase
(project `blcoiejnzrdxjwgxmlui`).

```bash
SUPABASE_SERVICE_KEY=... python scripts/sync_to_stl_rv.py --dry-run         # preview
SUPABASE_SERVICE_KEY=... python scripts/sync_to_stl_rv.py --slug jayco      # one brand
SUPABASE_SERVICE_KEY=... python scripts/sync_to_stl_rv.py                   # full sync
SUPABASE_SERVICE_KEY=... python scripts/sync_to_stl_rv.py --skip-images     # mfrs+models+floorplans only
```

The sync is idempotent and diff-based. Natural keys:

- `manufacturers`: name
- `models`: (manufacturer_id, model_name, model_year)
- `floorplans`: (model_id, floorplan_code)
- `kb_images`: (model_id, source_url)

The sync never deletes. It only inserts new rows and PATCHes changed fields.

## Files for resume-safe context

| File | Role |
|---|---|
| `CLAUDE.md` | Entry point for a fresh Claude Code session. Read first. |
| `STATE.md` | Current truth: what's built, what does NOT work, env vars, next task. |
| `SESSION-LOG.md` | Append-only session log. Most-recent block first. |
| `PLAN.md` | Roadmap + scraper history per brand. |
| `CHANGELOG.md` | High-level change log. |

## Known gaps

- All extracted images are `image_type='exterior'` — no floorplan PNGs yet.
  Downstream consumers that want floorplan images fall back to model-level
  exterior shots.
- No automated test suite. Verification is dashboard + `--dry-run` on sync.
- `mcp/` directory is a placeholder for a future MCP wrapper.

See `STATE.md` for the live gap list.
