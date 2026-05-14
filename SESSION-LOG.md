# Session Log

## 2026-05-13 — Floorplan image classifier + 2,361-row backfill

**Goal:** unblock STL RV's `/api/floorplans/find-image` consumer, which has
been returning nothing for every model because rv-catalog had zero
`image_type='floorplan'` rows. All 18,484 catalog images were hardcoded to
`'exterior'` at insert time in `base.py::_persist`.

**Approach:** URL-based classifier, no scraping change required. Same
classifier in two places:
- `backend/scrapers/base.py::GenericScraper._classify_image_type` —
  used at insert time so future scrapes tag correctly.
- `scripts/reclassify_image_types.py` — standalone, idempotent, dry-run
  supported. Backfilled the existing 18,484 rows.

**Classifier shape (after three rounds of false-positive analysis):**
- Negate: `interior` anywhere in URL (catches Drupal's
  `floorplan_interiors_thumb` image-style — 241 Alliance rows were misclassed
  by the naive substring check).
- Accept: `floorplan` / `floor-plan` / `floor_plan` token in the *filename*
  (Alliance, Airstream, Brinkley, Coachmen, Forest River).
- Accept: `/floorplans/` (plural) anywhere in URL — Grand Design, Brinkley,
  Winnebago dynamic GetImage.ashx URLs (Image=/...../Floorplans/...png in
  query string), KZ, Starcraft/Highland-Ridge `/uploads/rvs/floorplans/`.
- Accept singular `/floorplan/` only when filename has none of `paint`,
  `graphics`, `decor`, `swatch`, `lifestyle`, `-img-`, `_img-`, `img_`. The
  singular path is used by Jayco/Starcraft/Highland-Ridge as a CMS upload
  bucket for mixed content (paint schemes, feature shots, lifestyle photos);
  Lance's CDN uses it cleanly with code-only filenames.

**Verification before applying:**
- Jayco: 51 URLs with `/floorplan/` token, classifier flagged 0 as
  floorplan (all FPs correctly excluded — Jayco doesn't publish line-art
  floorplan PNGs at all).
- Lance/Grand Design/Brinkley/Airstream/Winnebago — all known TPs survive.
- Final dry-run delta: 2,361 rows flip exterior → floorplan, no extras.

**Apply:**
- DB backup: `data/rv_catalog.db.bak.reclassify-20260513-202308` (7.7 MB).
- `python scripts/reclassify_image_types.py` updated 2,361 rows.
- Post-state: 16,123 exterior / 2,361 floorplan.

**Top brands gaining floorplan rows:**
grand-design 670, coachmen 292, forest-river 158, lance 107, kz 89,
rockwood 82, flagstaff-rv 82, genesis-supreme 75, newmar 65, venture 55,
east-to-west 48, airstream 46, highland-ridge 44, palomino 42,
gulf-stream 36, prime-time 34, brinkley 31, fleetwood 26, tiffin 25,
dynamax 22, holiday-rambler 21, cherokee-rv 19.

**Files changed:**
- `backend/scrapers/base.py` — added `_classify_image_type` classmethod and
  rewired `_persist` to call it per-URL.
- `scripts/reclassify_image_types.py` (new) — backfill, dry-run, --slug
  scope, --db override.

**Not done:**
- Task #1 (drop NOT NULL on STL RV `kb_images.local_path`) still pending
  Adam runs the SQL. Once dropped, the next sync run will push the 2,361
  floorplan-tagged rows into STL RV and `/api/floorplans/find-image` will
  start returning hits.

## 2026-05-13 — STL RV sync gap audit + resume-safe docs

**Goal:** clear STATE.md's "What does NOT work" list.

**Diagnoses revised after live probing:**

1. `kb_images.local_path NOT NULL` — *confirmed* the column is NOT NULL, but
   the constraint sequence (`model_name` → `image_type` → `local_path` all NOT
   NULL) made an earlier sentinel test mis-report. Verified by running an
   actual `python scripts/sync_to_stl_rv.py --slug jayco` and reading the
   exact PostgREST 23502 error.
2. `floorplans.image_url` populating gap — *false alarm.* It's a cache, not a
   sync target. STL RV's consumer (`stl-rv-website/server/main.py:953-1004`)
   falls back through `inventory_images` → `kb_images`. The blocker is
   upstream: rv-catalog has zero `image_type='floorplan'` rows. All 18,484
   images are `image_type='exterior'` and zero have `floorplan_id` set.
   Scraper roadmap problem, not a sync-script problem.
3. PLAN.md API shapes — *stale.* `/api/images?model_id=X` doesn't exist;
   image rows are bundled into `/api/models/{model_id}` responses. Scrape
   trigger is `POST /api/scrape/trigger` with `{slug:...}` body, not
   `POST /api/scrape/{slug}`. Updated to reflect actual routes from
   `backend/routers/*`.

**Files changed:**
- `scripts/sql/stl_rv_drop_local_path_not_null.sql` (new) — DDL for Adam to
  paste into Supabase SQL Editor for project `blcoiejnzrdxjwgxmlui`. Drops
  NOT NULL on `kb_images.local_path` because the consumer code at
  `stl-rv-website/server/main.py:1000` already treats it as optional
  (`source_url or local_path`). Adam picked this over synthesizing junk paths.
- `PLAN.md` — API Endpoints section rewritten with current routes + params.
- `STATE.md` — Gap list refreshed; immediate-next-task points to running the
  SQL then rerunning sync.
- `CLAUDE.md` (new) — entry-point doc for fresh Claude sessions.
- `README.md` (new) — project overview + commands.

**Verified:**
- `python scripts/sync_to_stl_rv.py --slug jayco --dry-run` clean.
- `python scripts/sync_to_stl_rv.py --slug jayco` (apply) succeeds for
  manufacturers/models/floorplans, fails at kb_images on the NOT NULL.
- Image audit confirmed: 0 rows have `image_type='floorplan'` or
  `floorplan_id` set across all 18,484 images.

**Side findings (not fixed):**
- `stl-rv-website/scripts/migrate_to_supabase.py:7` has a hardcoded Supabase
  service-role key. Belongs in `.env` or Secret Manager, not committed. Filed
  in STATE.md as a non-blocking security TODO.
- `mcp/` is genuinely empty (untracked, no git history). PLAN.md "Future"
  references the MCP wrapper. Left as placeholder, documented in STATE.md.

**Not done:** Adam needs to run the SQL before the sync can finish. After
that, the kb_images backfill is one command.

## 2026-05-11 — Bootstrap session

Resume-safe docs created from existing state. STATE.md generated by reading:
- Top-level directory listing (`.`)
- `dashboard/README.md`
- `dashboard/package.json`
- `backend/main.py`
- `backend/requirements.txt`
- `backend/routers/health.py`
- `backend/routers/manufacturers.py`
- `backend/routers/models.py`
- `backend/routers/scrape.py`
- `backend/database.py`
- `backend/auth.py`
- `cloudbuild.yaml`
- `Dockerfile`
- `PLAN.md`
- `CHANGELOG.md`
- `dashboard/src/api.ts`
- `dashboard/src/App.tsx`
- `dashboard/src/auth.tsx`
- `dashboard/src/pages/Overview.tsx`
- `dashboard/src/pages/Manufacturers.tsx`
- `dashboard/src/pages/ManufacturerDetail.tsx`
- `dashboard/src/pages/ScrapeRuns.tsx`
- `scripts/sync_to_stl_rv.py`
- `scripts/run_scraper.py`
- `backend/scrapers/orchestrator.py`
- `.env` variable names only
- Most recent commits (if a git repo): `d1641df PLAN.md: STL RV sync state + next-session floorplan gap`; `bc4c081 Sync: int coercion + half-bath split + mfr synthetic dry-run IDs`; `95da801 docs: update CHANGELOG.md`

No code changes this session. Next session: see STATE.md "Immediate next task".
