# Project State

## Status

RV Catalog is a standalone FastAPI + React/Vite service that owns RV manufacturer, model, floorplan, and image data for dealer-site reuse. It is actively in development/ops: the local SQLite catalog is populated, the Cloud Run deployment config exists, and the most recent work is the STL RV Supabase sync/image-flow follow-up.

## What's built and wired

- FastAPI app entry point is `backend/main.py` (`backend.main:app`). It initializes SQLite through `backend/database.py`, mounts built dashboard assets from `dashboard/dist` when present, exposes `/api-docs` in development only, and runs on `PORT` with default `8080`.
- Auth is wired in `backend/auth.py`: development mode returns a fake user, production expects Google ID tokens and checks `ALLOWED_DOMAIN`. Public auth config is `GET /api/auth/config`; authenticated user echo is `GET /api/auth/me`.
- Protected API routers are included from `backend/routers/`:
  - `GET /api/health` and `GET /api/health/manufacturer/{slug}` in `backend/routers/health.py`
  - `GET /api/manufacturers` and `GET /api/manufacturers/{slug}` in `backend/routers/manufacturers.py`
  - `GET /api/models`, `GET /api/models/{model_id}`, `GET /api/floorplans`, `GET /api/floorplans/{floorplan_id}`, and `GET /api/lookup?make=...&model=...&year=...` in `backend/routers/models.py`
  - `GET /api/scrape/runs`, `GET /api/scrape/active`, and `POST /api/scrape/trigger` in `backend/routers/scrape.py`
- SQLite database path is `data/rv_catalog.db`. `backend/database.py` defines `parent_companies`, `manufacturers`, `models`, `floorplans`, `images`, and `scrape_runs`.
- Current local DB counts verified on 2026-05-11: 93 manufacturers, 83 active manufacturers, 10 defunct manufacturers, 1,324 models, 3,650 floorplans, 18,484 images, and 448 scrape runs. Manufacturer scrape statuses are `complete:66`, `partial:16`, `error:3`, `defunct:8`.
- Dashboard is `dashboard/` with Vite/React/TypeScript. `dashboard/src/App.tsx` routes `/`, `/manufacturers`, `/manufacturers/:slug`, and `/scrape`; `dashboard/src/api.ts` calls the backend API; `dashboard/src/auth.tsx` handles Google Identity Services and development-mode bypass.
- Scraper CLI is `scripts/run_scraper.py`: supports `--slug`, `--wave`, and `--all`, requires `GEMINI_API_KEY`, and calls `backend/scrapers/orchestrator.py`. Scrape runs are recorded in `scrape_runs`.
- STL RV sync is `scripts/sync_to_stl_rv.py`: one-way SQLite to STL RV Supabase, diff-based and idempotent, with `--dry-run`, `--slug`, and `--skip-images`. Natural keys are manufacturer name, `(manufacturer_id, model_name, model_year)`, `(model_id, floorplan_code)`, and `(model_id, source_url)`.
- Docker deployment is wired in `Dockerfile`: builds the dashboard with Node 20, installs FastAPI/Playwright on Python 3.12, copies `backend/`, `scripts/`, and `data/`, seeds if the copied DB is empty, serves `backend.main:app` on port `8080`.
- Cloud Build deployment is wired in `cloudbuild.yaml`: builds/pushes an image and deploys Cloud Run service `rv-catalog` in `us-central1`.

## What does NOT work yet / known gaps

- **STL RV `kb_images.local_path` NOT NULL — SQL written, waiting on apply.**
  `scripts/sql/stl_rv_drop_local_path_not_null.sql` drops the constraint on
  STL RV's table (project `blcoiejnzrdxjwgxmlui`). Adam to paste into Supabase
  SQL Editor. Verified 2026-05-13 the constraint is still in place. Once
  dropped, rerun `python scripts/sync_to_stl_rv.py` (no `--skip-images`) and
  the image sync proceeds; the consumer (`stl-rv-website/server/main.py:1000`)
  already prefers `source_url` over `local_path`. See SESSION-LOG.md 2026-05-13
  for the audit that identified the actual blocker.
- **`floorplans.image_url` is NOT a sync target.** Earlier STATE.md treated
  this as a populating gap. Reality: the column is a per-floorplan image cache.
  STL RV's `/api/floorplans/find-image` falls through `inventory_images` →
  `kb_images` (filtered by `image_type='floorplan'`). rv-catalog has zero
  `image_type='floorplan'` rows today — all 18,484 images are 'exterior'. Two
  follow-ups: (a) scraper roadmap item to extract real floorplan PNGs; (b)
  consider relaxing STL RV's filter to accept 'exterior' as a fallback so the
  UI shows something instead of nothing.
- Low-image active brands currently under 15 images: `shasta`, `crossroads`,
  `ember`, `outdoors-rv`, `scamp`, `bowlus`, `northern-lite`, `hiker`,
  `sandpiper`, `sierra`, `surveyor`, `xlr-toy-hauler`, `vengeance`.
- No automated test suite. Verification is dashboard + `--dry-run` on sync.
  TODO: at minimum a smoke test that hits `/api/health` and one
  manufacturer/model/floorplan endpoint.
- `mcp/` is an empty placeholder for the future MCP wrapper called out in
  `PLAN.md` "Future". Not a bug; tracked here so it doesn't show up as a
  surprise.
- **Security TODO (not blocking this work):** the STL RV repo has a hardcoded
  service-role key at `stl-rv-website/scripts/migrate_to_supabase.py:7`. That
  belongs in `.env` or Secret Manager, not in a committed file.

## Ports / URLs / env vars / secrets

- Backend port: `8080` by default (`PORT` in `backend/main.py`, `EXPOSE 8080` in `Dockerfile`).
- Dashboard dev server: `npm run dev` in `dashboard/package.json` uses Vite defaults. TODO: confirm local port if overridden outside the repo.
- API base path used by dashboard: `/api`.
- Production dashboard is served from `/` when `dashboard/dist` exists.
- Development API docs path: `/api-docs`.
- Env var names seen in code or `.env` names: `ENVIRONMENT`, `PORT`, `GOOGLE_CLIENT_ID`, `ALLOWED_DOMAIN`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `RV_HOME_PROXY_POOL`, `CD_HOME_PROXY_POOL`, `PROXY_POOL`, `RV_PROXY_PROBE_TIMEOUT`, `RV_PROXY_PROBE_TTL`, `STEALTH_HEADLESS`, `STEALTH_TIMEOUT_MS`, `STEALTH_NODE`, `STEALTH_SCRIPT`, `CD_IPROYAL_USER`, `CD_IPROYAL_PASS`.
- Secret handling rule: keep secret values only in `.env` or GCP Secret Manager, never in committed files.

## Deployment

- Cloud Run service: `rv-catalog`.
- GCP project: `savvydealer-website` per `PLAN.md`; `cloudbuild.yaml` itself uses `$PROJECT_ID`.
- Region: `us-central1`.
- Container image path pattern: `us-central1-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/rv-catalog:$SHORT_SHA`.
- Cloud Build trigger: TODO: confirm trigger name/source.
- Public service URL / custom domain: TODO: confirm. `PLAN.md` says dashboard URL is TBD.

## Immediate next task

1. Adam runs `scripts/sql/stl_rv_drop_local_path_not_null.sql` in Supabase SQL
   Editor (project `blcoiejnzrdxjwgxmlui`).
2. `SUPABASE_SERVICE_KEY=... python scripts/sync_to_stl_rv.py` (full sync).
3. Verify a few `kb_images` rows landed and spot-check the dealer-site
   floorplan card for one Jayco model.
4. Optional follow-ups: scraper change to extract floorplan-typed PNGs;
   smoke test added to repo.

## Last verified

2026-05-13
