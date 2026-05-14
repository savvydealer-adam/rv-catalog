# RV Catalog — Claude Code entry point

**If you just landed here with a fresh context, read this first, then `STATE.md`.**

Adam clears Claude Code context between pushes. This repo's markdown is the
handoff surface. Don't rediscover what the last session already wrote down.

## 10-second orientation

Central RV knowledge base. Owns manufacturer, model, floorplan, and image data
for every active RV OEM (currently 93 mfrs / 83 active / 1,324 models / 3,650
floorplans / 18,484 images). Dealer websites (STL RV, future RV dealers) call
this API instead of maintaining their own knowledge bases.

Standalone FastAPI service. SQLite locally; the same SQLite is bundled into the
Cloud Run image (single-tenant catalog, not customer data). Admin dashboard
ships at `/` when `dashboard/dist` is built.

## Where to read before editing

| File | Purpose |
|---|---|
| `STATE.md` | **What's built, what's wired, what does NOT work, ports + env vars + next task.** Current as of the last push. |
| `SESSION-LOG.md` | Chronological log of each session's work. Scan the most recent block. |
| `PLAN.md` | Long-form roadmap + per-brand scraper history. Heaviest source of context but mostly chronological lore. |
| `CHANGELOG.md` | High-level change log. |

## Where code lives

```
backend/
  main.py                FastAPI app entry (mounts dashboard, routes /api/*)
  database.py            SQLite schema + init
  auth.py                Google ID token check; dev mode auto-stub
  routers/               manufacturers / models / health / scrape
  scrapers/
    orchestrator.py      Parallel wave runner
    base.py              GenericScraper + Gemini 2.5 Flash extraction
    brand_configs.py     Per-brand listing_pages, model_urls, force_stealth, etc.
    playwright_fetcher.py  JS-render layer (proxy-aware)
    stealth_fetcher.py     puppeteer-real-browser subprocess bridge (WAF bypass)
dashboard/               React/Vite admin dashboard
data/rv_catalog.db       SQLite catalog (bundled into the image)
scripts/
  run_scraper.py         CLI: --slug, --wave, --all (needs GEMINI_API_KEY)
  run_missing.py         Backfill brands with 0 models
  sync_to_stl_rv.py      One-way SQLite -> STL RV Supabase (`blcoiejnzrdxjwgxmlui`)
  qwen_site_recon.py     Ollama-powered site structure analysis
  sql/                   One-shot DDL helpers for downstream Supabases
  stealth/               Node project: puppeteer-real-browser CLI
mcp/                     Placeholder for future MCP wrapper (empty)
Dockerfile, cloudbuild.yaml   Cloud Run deploy: service `rv-catalog`, project `savvydealer-website`, region us-central1
```

## How to run things

```bash
# Local backend (default port 8080):
ENVIRONMENT=development python -m uvicorn backend.main:app --reload

# Scrape one brand:
GEMINI_API_KEY=... python scripts/run_scraper.py --slug jayco

# Sync catalog to STL RV (production Supabase):
SUPABASE_SERVICE_KEY=... python scripts/sync_to_stl_rv.py            # full
SUPABASE_SERVICE_KEY=... python scripts/sync_to_stl_rv.py --dry-run --slug jayco
```

No standalone test suite yet — verification is done via `--dry-run` on the sync
script and by exercising the dashboard. TODO: add a smoke test.

## Rules Adam has set for this project

- **STATE.md and SESSION-LOG.md must stay current after every session.** Don't
  push code changes without updating both.
- **One-way data flow to dealer sites.** `sync_to_stl_rv.py` and any future
  per-dealer sync script is the only path. Never bidirectional.
- **Image data is `source_url`-first.** rv-catalog doesn't download or host the
  images — it stores the OEM URL. Downstream Supabases can synthesize GCS
  paths if they need their own CDN copy.
- **Don't add new Supabase projects.** Adam is consolidating; new internal
  tools default to the `savvy-ops-01` VPS unless they need Supabase
  specifically.
- **`floorplans.image_url` in STL RV is a CACHE, not a sync target.** Consumer
  endpoint (`/api/floorplans/find-image`) falls back through `inventory_images`
  → `kb_images`. The sync script populates `kb_images`, not `image_url`.

## Watch out

- The SQLite DB is bundled into the Cloud Run image. Local edits to
  `data/rv_catalog.db` are NOT reflected in production until the image is
  rebuilt and redeployed via `cloudbuild.yaml`.
- The scraper currently produces only `image_type='exterior'` rows — no
  floorplan PNGs are extracted yet. Treat that as a known gap; STATE.md
  tracks it.
- `data/`, `data/*.db.bak.*`, and `.env` are gitignored. Don't try to recover
  state from git.
