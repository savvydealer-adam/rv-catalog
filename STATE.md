# Project State

## Status

RV Catalog is a standalone FastAPI + React/Vite service that owns RV manufacturer, model, floorplan, and image data for dealer-site reuse. It is actively in development/ops: the local SQLite catalog is populated, the Cloud Run deployment config exists, and the most recent work is the STL RV Supabase sync/image-flow follow-up.

> **2026-10-27:** STL RV's database is moving off hosted Supabase to the ops-01 self-hosted Supabase
> (`https://sb.savvycdn.us`, schema `stlrv`; CUT OVER 2026-10-27 — use the ops-01 settings below). After cutover run the sync with
> `SUPABASE_URL=https://sb.savvycdn.us SUPABASE_SCHEMA=stlrv SUPABASE_SERVICE_KEY=<GSM savvy-comms-vps-service-role-key>`.

## What's built and wired

- FastAPI app entry point is `backend/main.py` (`backend.main:app`). It initializes SQLite through `backend/database.py`, mounts built dashboard assets from `dashboard/dist` when present, exposes `/api-docs` in development only, and runs on `PORT` with default `8080`.
- Auth is wired in `backend/auth.py`: development mode returns a fake user, production expects Google ID tokens and checks `ALLOWED_DOMAIN`. Public auth config is `GET /api/auth/config`; authenticated user echo is `GET /api/auth/me`.
- Protected API routers are included from `backend/routers/`:
  - `GET /api/health` and `GET /api/health/manufacturer/{slug}` in `backend/routers/health.py`
  - `GET /api/manufacturers` and `GET /api/manufacturers/{slug}` in `backend/routers/manufacturers.py`
  - `GET /api/models`, `GET /api/models/{model_id}`, `GET /api/floorplans`, `GET /api/floorplans/{floorplan_id}`, and `GET /api/lookup?make=...&model=...&year=...` in `backend/routers/models.py`
  - `GET /api/scrape/runs`, `GET /api/scrape/active`, and `POST /api/scrape/trigger` in `backend/routers/scrape.py`
- SQLite database path is `data/rv_catalog.db`. `backend/database.py` defines `parent_companies`, `manufacturers`, `models`, `floorplans`, `images`, and `scrape_runs`.
- Current local DB counts (2026-05-13): 93 manufacturers (83 active, 10
  defunct), 1,324 models, 3,650 floorplans, 18,484 images, 448 scrape runs.
  Manufacturer scrape statuses: `complete:66`, `partial:16`, `error:3`,
  `defunct:8`. Image types: 16,123 `exterior` / 2,361 `floorplan` after the
  2026-05-13 URL-based reclassification.
- Dashboard is `dashboard/` with Vite/React/TypeScript. `dashboard/src/App.tsx` routes `/`, `/manufacturers`, `/manufacturers/:slug`, and `/scrape`; `dashboard/src/api.ts` calls the backend API; `dashboard/src/auth.tsx` handles Google Identity Services and development-mode bypass.
- Scraper CLI is `scripts/run_scraper.py`: supports `--slug`, `--wave`, and `--all`, requires `GEMINI_API_KEY`, and calls `backend/scrapers/orchestrator.py`. Scrape runs are recorded in `scrape_runs`.
- STL RV sync is `scripts/sync_to_stl_rv.py`: one-way SQLite to STL RV Supabase, diff-based and idempotent, with `--dry-run`, `--slug`, and `--skip-images`. Natural keys are manufacturer name, `(manufacturer_id, model_name, model_year)`, `(model_id, floorplan_code)`, and `(model_id, source_url)`.
- Docker deployment is wired in `Dockerfile`: builds the dashboard with Node 20, installs FastAPI/Playwright on Python 3.12, copies `backend/`, `scripts/`, and `data/`, seeds if the copied DB is empty, serves `backend.main:app` on port `8080`.
- Cloud Build deployment is wired in `cloudbuild.yaml`: builds/pushes an image and deploys Cloud Run service `rv-catalog` in `us-central1`.

## What does NOT work yet / known gaps

- ~~STL RV `kb_images.local_path` NOT NULL~~ — **DONE 2026-05-14.** Constraint
  dropped via Supabase Management API (using `SUPABASE_ACCESS_TOKEN` from
  `~/.claude/mcp.json`). Full sync ran; STL RV now has 19,104 kb_images,
  2,420 of them `image_type='floorplan'`. Per-brand parity confirmed against
  rv-catalog SQLite.
- **`floorplans.image_url` is NOT a sync target.** Earlier STATE.md treated
  this as a populating gap. Reality: the column is a per-floorplan image
  cache. STL RV's consumer endpoint (now `/api/knowledge/floorplan-image` in
  `stl-rv-website/server/main.py`, formerly `/api/floorplans/find-image`)
  falls through `inventory_images` → `kb_images` (filtered by
  `image_type='floorplan'`).
  After the 2026-05-13 reclassification, the catalog now has 2,361 rows tagged
  `image_type='floorplan'` (12.8% of 18,484), so STL RV's fallback path will
  finally find images for ~30 brands once Task #1 unblocks the sync. The
  remaining model-level lifestyle/exterior shots stay `image_type='exterior'`.
  Backfill script: `scripts/reclassify_image_types.py`. Classifier mirrored
  in `backend/scrapers/base.py::GenericScraper._classify_image_type` so
  future scrapes tag correctly. DB backup at
  `data/rv_catalog.db.bak.reclassify-20260513-*`.
- Low-image active brands currently under 15 images: `shasta`, `crossroads`,
  `ember`, `outdoors-rv`, `scamp`, `bowlus`, `northern-lite`, `hiker`,
  `sandpiper`, `sierra`, `surveyor`, `xlr-toy-hauler`, `vengeance`.
- ~~**`flagstaff-rv` scrape extracts 0 models (2026-10-18).**~~ **FIXED
  2026-10-21.** Root cause: `forestriverinc.com` now Cloudflare-challenges
  plain httpx *and* local headless Playwright ("Just a moment...", HTTP 403),
  and the 2026 site rebuild moved model pages under `/rvs/travel-trailers/`
  (old `/rvs/flagstaff-*` and root `/flagstaff-*` slugs soft-404 as HTTP 200).
  Fixes: (1) `backend/scrapers/base.py` detects CF challenge interstitials
  (`_is_cf_challenge`) and raises a visible `RuntimeError` when every fetcher
  hands back the interstitial or a WAF block instead of silently dropping the
  model to None; the stealth path gets one settle+retry on a challenge hit.
  (2) `brand_configs.py` routes `flagstaff-rv` through the stealth node
  (`force_stealth: True`) with the 8 current model URLs seeded from the live
  entry page `/rvs/travel-trailers/flagstaff` (Hardside Pop-Up retired;
  A-Frame and Tent are its successors). Re-scrape: 8/8 models extracted,
  73 floorplans, 130 images, 0 errors (run `success`, 135s). DB: 169 → 299
  images (212 exterior / 87 floorplan), 82 → 155 floorplans. Read-only
  probe: `scripts/flagstaff_diagnose.py`.
- ~~No automated test suite.~~ **DONE 2026-10-14.** `tests/test_api.py` is a
  hermetic smoke suite (17 tests): temp SQLite with the real schema + a small
  seed, `ENVIRONMENT=development` (auth stub). Covers `/api/health`,
  manufacturers, models, floorplans, `/api/lookup`, and `/api/auth/*`.
  `python -m pytest tests/ -q` — no DB setup, no network, passes on a fresh
  clone. The suite caught three real bugs, fixed the same day:
  (1) `SCHEMA_SQL` was missing `manufacturers.defunct` — a freshly created
  DB would 500 on every endpoint (routers query `COALESCE(defunct,0)`);
  (2) all four 404 paths returned the **tuple** `({"error": "Not found"}, 404)`,
  which FastAPI serializes as a 200 JSON array — now real
  `HTTPException(404)`; (3) `/api/lookup` selected
  `mfr.display_name as manufacturer_display` but `_model_row()` dropped it
  from the response — now included in `match`.
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

No blocking gap. Optional follow-ups (priority-ordered):

1. ~~Spot-check the STL RV floorplan image endpoint.~~ **VERIFIED 2026-10-14
   live.** `GET /api/knowledge/floorplan-image` on
   `https://stl-rv-prod-952362582307.us-central1.run.app` returns
   `{"source": "kb"}` with a real image URL for Grand Design RV (Solitude
   382WB), Coachmen RV (Phoenix), and Lance Camper (Lance Truck Campers); all
   three image URLs resolve 200 with valid image content types. Note: the old
   `crm.savvydealer.ai` reference in this file was the wrong site (Savvy
   Dealer AI CRM, a Replit SPA) — the STL RV dealer site is the Cloud Run
   URL above. Caveat: the kb fallback is model-level — it returns the first
   floorplan-typed image for the model, not one matching the requested
   `floorplan_code` (code is embedded in the image URL; the consumer
   `stl-rv-website` is responsible for exact-code matching).
2. Move + rotate the hardcoded service-role key at
   `stl-rv-website/scripts/migrate_to_supabase.py:7` (rotate in Supabase,
   replace literal with `os.getenv("SUPABASE_SERVICE_KEY")`). This lives in
   the `stl-rv-website` repo, not this one.
3. ~~Add `tests/test_api.py` smoke suite.~~ **DONE 2026-10-14** (see gaps).
4. ~~Re-scrape low-image brands (roadtrek, flagstaff-rv, ibex, sabre).~~
   **DONE 2026-10-18.** roadtrek 88→368 images (+280; 11 new floorplan-type),
   sabre 290→346, ibex 110→122, flagstaff-rv unchanged (0 extracted — see
   gap). Catalog totals: 18,832 images / 2,372 floorplan-type.
5. **PENDING HUMAN (re-parked 2026-10-26 in #claude-ops; dry-run re-verified
   2026-10-21 and again 2026-10-26 — identical diff, no drift):**
   apply the STL RV sync — dry-run now shows kb_images inserts=478
   (348 pre-flagstaff + 130 new), floorplans inserts=104 (+73), models
   inserts=31 (+8); 0 deletes, models/floorplans also carry field updates
   (models updates=116, floorplans updates=196). The 2026-10-18 park's TTL
   lapsed with zero replies, so it was re-parked 2026-10-26 (escalate.py,
   channel C0BAUTCAT0Q, ts 1793004629.975179). If approved: inject
   `SUPABASE_SERVICE_KEY` from GCP secret
   `supabase-service-key-stl-rv` (project `savvydealer-website`) via
   `savvy-secrets` `access_secret()`, then `python scripts/sync_to_stl_rv.py`;
   confirm kb_images inserts=478 and re-run `python -m pytest tests/ -q`.
   Customer-facing write to the STL RV dealer site — waits for approval.
6. Future: extract floorplan PNGs from sites where current scraper misses
   them (deeper scraper work).

**Next-session prompt:** Resume rv-catalog at C:/Users/adam/rv-catalog — read STATE.md first. All code gaps are closed; the ONLY open item is the STL RV sync apply, re-parked 2026-10-26 in #claude-ops (channel C0BAUTCAT0Q, ts 1793004629.975179) because it is a customer-facing write to the live dealer site and the 10-18 park lapsed with zero replies. The dry-run diff was re-verified 2026-10-26 (identical to 10-21: models inserts=31 updates=116, floorplans inserts=104 updates=196, kb_images inserts=478, 0 deletes) and `python -m pytest tests/ -q` passed 17/17. Check the #claude-ops thread / pending-decision journal for a reply: if approved, inject `SUPABASE_SERVICE_KEY` from GCP secret `supabase-service-key-stl-rv` (project `savvydealer-website`) via savvy-secrets and run `python scripts/sync_to_stl_rv.py` (or `--slug <brand>` if the single-brand option was picked), confirm the inserts, re-run the tests, mark item 5 done. Otherwise: no work — do not re-park (TTL 48h); just note the dry-run if it has drifted. Future: extract floorplan PNGs from sites where the scraper misses them.

## Last verified

2026-10-26
