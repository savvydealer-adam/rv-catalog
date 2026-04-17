# RV Catalog -- Central RV Knowledge Base & API

## What This Is

A standalone service that owns all RV manufacturer, model, and floorplan data. Dealer websites (STL RV, future sites) call this API instead of maintaining their own knowledge bases. Includes an admin dashboard for monitoring coverage across 60+ manufacturers.

## Current State (2026-04-17)

**Coverage:** 93 manufacturers seeded, 54 with scraped data (58%), 484 models, 842 floorplans, 3,111 images.

**Infra shipped:** IPRoyal residential proxy (rotating, bare auth via `CD_IPROYAL_USER/PASS`), Qwen3:32b recon pipeline (`scripts/qwen_site_recon.py`), per-brand configs with `model_path_patterns` and `force_stealth` escape hatches, **stealth fetcher** (puppeteer-real-browser, local PC, bypasses Cloudflare/Akamai without proxy).

**Stealth stack (2026-04-17):**
- `scripts/stealth/stealth_fetch.js` -- puppeteer-real-browser CLI (rebrowser-puppeteer-core + ghost-cursor + Turnstile auto-solve). Non-headless Chrome on local PC; residential IP + real Chrome fingerprint bypass WAF fingerprinting. No proxy.
- `backend/scrapers/stealth_fetcher.py` -- subprocess adapter; `force_stealth: True` in `brand_configs.py` routes a brand's fetches through it. Also auto-falls-back from httpx 403 → stealth.
- Node deps isolated in `scripts/stealth/package.json` (puppeteer-real-browser 1.4.4).
- **Proven:** heartland (Cloudflare WAF) went 0 -> 8 models / 25 floorplans / 160 images.

**Scripts:**
- `scripts/run_scraper.py` -- single brand or wave
- `scripts/run_missing.py` -- all brands with 0 models (`--only`, `--skip`)
- `scripts/qwen_site_recon.py` -- Ollama-powered site structure analysis
- `scripts/backup_to_md.py` -- markdown backup snapshots

## Architecture

```
rv-catalog/
  backend/          FastAPI REST API + scraping pipeline
    routers/        API route modules
    scrapers/       Per-manufacturer scraper modules
      base.py           GenericScraper + Gemini 2.5 Flash extraction
      brand_configs.py  34 per-brand listing_pages + force_playwright
      playwright_fetcher.py  JS render, IPRoyal proxy, SPA wait
      orchestrator.py   Parallel wave runner
  dashboard/        React/Vite admin dashboard (coverage monitor)
  mcp/              MCP server wrapper (for Claude Code access)
  data/             SQLite databases
  scripts/          Seed scripts, scrapers, recon tools
```

**Deployment:** Cloud Run (`savvydealer-website` project), service name `rv-catalog`
**Database:** SQLite (bundled in container) -- upgrade to Cloud SQL if it outgrows this
**Dashboard URL:** TBD (rv-catalog.savvydealer.com or similar subdomain)

## API Endpoints (consumed by dealer websites)

```
GET  /api/manufacturers                    List all manufacturers
GET  /api/manufacturers/{id}               Manufacturer detail + models
GET  /api/models?make=X&year=Y&class=Z     Search models
GET  /api/models/{id}                      Model detail + floorplans
GET  /api/floorplans?model_id=X            Floorplans for a model
GET  /api/floorplans/{id}                  Floorplan detail + specs
GET  /api/lookup?make=X&model=Y&year=Z     Quick lookup (for inventory enrichment)
GET  /api/images?model_id=X                Images for a model
GET  /api/health                           Coverage stats for dashboard
GET  /api/health/manufacturer/{id}         Per-manufacturer completeness
POST /api/scrape/{manufacturer_slug}       Trigger scrape (admin, auth required)
```

## Scraping Pipeline

### How it works
1. `_discover_models` — tries brand_configs listing_pages, then sitemap.xml, then generic paths
2. `_ai_find_model_links` — Gemini classifies anchor tags as model-page links vs. category/nav
3. `_extract_model` — fetches each URL (httpx → Playwright fallback), Gemini extracts structured JSON
4. `_persist` — stores models + floorplans + images in SQLite

### Proxy layer
IPRoyal rotating-residential (NO sticky sessions — bare `user:pass@geo.iproyal.com:12321` auth only, any username suffix → HTTP 407). Shared credentials with competitive-dashboard via GCP Secret Manager (`iproyal-proxy-user`/`iproyal-proxy-pass`).

### brand_configs.py (34 entries)
Hand-curated: thor-motor-coach, winnebago, heartland, coachmen, forest-river, keystone, dutchmen, airstream, highland-ridge, cherokee-rv, alliance, brinkley, fleetwood, gulf-stream, tiffin, crossroads.

Qwen3-proposed (2026-04-16): aliner, bigfoot, bowlus, coach-house, cruiser-rv, dynamax, earthroamer, east-to-west, genesis-supreme, hiker, leisure-travel, northern-lite, northstar, outdoors-rv, prime-time, scamp, shasta, storyteller.

## Next Steps

### Critical: Fix model discovery hit rate
Only 4/26 new brands produced models on first scrape. Root cause: `_ai_find_model_links` confuses category pages for model pages. Options:
1. Add URL-depth heuristic (model URL depth > listing_page depth)
2. Use sitemap.xml more aggressively (strategy 2) before AI link classification
3. Add explicit `model_urls` lists to brand_configs for stubborn sites
4. Two-pass discovery: first pass finds category links, second pass follows them to find model links

### WAF-blocked brands -- RESOLVED 2026-04-17
- heartland: `force_stealth` → 8 models / 25 floorplans / 160 images.
- cherokee-rv: old `cherokeerv.com` domain was repurposed (now a campground site).
  Repointed to `forestriverinc.com/rvs/cherokee-black-label` (the only live series).
  → 15 models / ~22 floorplans / 328 images.
- cherokee-grey-wolf / arctic-wolf / wolf-pup: independent domains are dead
  (404 or redirect to promo landers). Keep as defunct rows unless they resurface.

### SPA filter-UI sites
- thor-motor-coach, coachmen — `force_stealth` alone doesn't help; models are behind
  filter-UI clicks. Coachmen 0→1, Thor still 0. Needs per-brand click-through scripts
  in `stealth_fetch.js` or explicit model-URL seed lists.
- winnebago — already has 22 models via pre-stealth scrape; revisit if coverage stalls.

### Dead / unreliable origins
- adventurermfg.com, encorerv.com, redwood-rv.com, raborv.com (renegade): 504 gateway timeout
- regencyrv.com: expired SSL cert
- Verify domains; mark defunct or find alternate URLs

### Sites with no category page (model-pages-only)
- fleetwood, holiday-rambler, travel-lite, american-coach, host, sunset-park, braxton-creek
- Needs: sitemap-based discovery or manual model URL list

### Future
- Cloud Run deploy with production DB
- MCP server wrapper
- API auth for dealer sites
- Image storage on GCS
- Rate limiting, caching
