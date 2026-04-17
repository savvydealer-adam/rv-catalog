# RV Catalog -- Central RV Knowledge Base & API

## What This Is

A standalone service that owns all RV manufacturer, model, and floorplan data. Dealer websites (STL RV, future sites) call this API instead of maintaining their own knowledge bases. Includes an admin dashboard for monitoring coverage across 60+ manufacturers.

## Current State (2026-04-17)

**Coverage:** 93 manufacturers seeded, 68 with scraped data (73%), 804 models, 1,405 floorplans, 5,033 images.

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
      base.py               GenericScraper + Gemini 2.5 Flash extraction
      brand_configs.py      Per-brand listing_pages + model_path_patterns
                            + force_playwright / force_stealth
      playwright_fetcher.py JS render, IPRoyal proxy, SPA wait
      stealth_fetcher.py    Bridge to scripts/stealth/ for WAF bypass
      orchestrator.py       Parallel wave runner
  dashboard/        React/Vite admin dashboard (coverage monitor)
  mcp/              MCP server wrapper (for Claude Code access)
  data/             SQLite databases
  scripts/          Seed scripts, scrapers, recon tools
    stealth/        Node project: puppeteer-real-browser CLI (stealth_fetch.js)
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
1. `_discover_models` — tries base_url, brand_configs listing_pages, then sitemap.xml, then generic paths
2. `_pattern_match_links` + `_ai_find_model_links` — pattern-based extraction supplements Gemini classification of anchor tags
3. `_extract_model` — fetches each URL (httpx → stealth/Playwright fallback), Gemini extracts structured JSON (accepts series pages with multiple floorplans as one model)
4. `_persist` — stores models + floorplans + images in SQLite

### Fetch layers (priority order)
1. **Stealth** — `force_stealth: True` or httpx 403 fallback. Calls `scripts/stealth/stealth_fetch.js` (puppeteer-real-browser) on the local PC. No proxy; real Chrome + residential IP bypass Cloudflare/Akamai WAF fingerprinting. Slow (~15-30s/page); batch only.
2. **Playwright + IPRoyal** — `force_playwright: True` or thin-content fallback. IPRoyal rotating-residential (NO sticky sessions — bare `user:pass@geo.iproyal.com:12321` auth only, any username suffix → HTTP 407). Shared creds with competitive-dashboard via GCP Secret Manager (`iproyal-proxy-user`/`iproyal-proxy-pass`).
3. **httpx** — default; fast, IPRoyal-routed when creds are set.

### brand_configs.py
Knobs per entry: `listing_pages`, `model_path_patterns`, `force_playwright`, `force_stealth`, `exclude_patterns`, `allow_external_domains`.

Hand-curated: thor-motor-coach, winnebago, heartland (**force_stealth**), coachmen, forest-river, keystone, dutchmen, airstream, highland-ridge, cherokee-rv, alliance, brinkley, fleetwood, gulf-stream, tiffin, crossroads.

Qwen3-proposed (2026-04-16): aliner, bigfoot, bowlus, coach-house, cruiser-rv, dynamax, earthroamer, east-to-west, genesis-supreme, hiker, leisure-travel, northern-lite, northstar, outdoors-rv, prime-time, scamp, shasta, storyteller.

## Next Steps

### Model discovery hit rate (ongoing)
`_pattern_match_links` (added 2026-04-17) now supplements the Gemini AI classifier — fixed Heartland where Gemini was dropping valid `/brand/<slug>/` URLs. For stubborn sites still returning 0, options:
1. Add `model_path_patterns` entries to brand_configs.
2. Add URL-depth heuristic (model URL depth > listing_page depth).
3. Use sitemap.xml more aggressively (strategy 2) before AI link classification.
4. Two-pass discovery: first pass finds category links, second pass follows to find models.

### WAF-blocked brands -- RESOLVED 2026-04-17
- heartland: `force_stealth` → 8 models / 25 floorplans / 160 images.
- cherokee-rv: old `cherokeerv.com` domain was repurposed (now a campground site).
  Repointed to `forestriverinc.com/rvs/cherokee-black-label` (the only live series).
  → 15 models / ~22 floorplans / 328 images.
- cherokee-grey-wolf / arctic-wolf / wolf-pup: independent domains are dead
  (404 or redirect to promo landers). **DEFUNCT 2026-04-17** — flagged in DB,
  excluded from `run_missing.py` and `/api/manufacturers` by default.

### SPA filter-UI sites
- thor-motor-coach, coachmen — `force_stealth` alone doesn't help; models are behind
  filter-UI clicks. Coachmen 0→1, Thor still 0. Needs per-brand click-through scripts
  in `stealth_fetch.js` or explicit model-URL seed lists.
- winnebago — already has 22 models via pre-stealth scrape; revisit if coverage stalls.

### Dead / unreliable origins -- DEFUNCT 2026-04-17
All five flagged `defunct=1` in `manufacturers` table; excluded from
`run_missing.py` target list and `/api/manufacturers` list endpoint by
default (pass `--include-defunct` / `?include_defunct=true` to force-include
if a domain resurfaces).

- adventurer (adventurermfg.com): 504 gateway timeout — **DEFUNCT 2026-04-17**
- encore (encorerv.com): 504 gateway timeout — **DEFUNCT 2026-04-17**
- redwood (redwood-rv.com): 504 gateway timeout — **DEFUNCT 2026-04-17**
- renegade (raborv.com): 504 gateway timeout — **DEFUNCT 2026-04-17**
- regency (regencyrv.com): expired SSL cert — **DEFUNCT 2026-04-17**

To un-defunct a brand (e.g. domain comes back online), run:
`UPDATE manufacturers SET defunct=0, scrape_status='not_started' WHERE slug='<slug>';`

### Sites with no category page (model-pages-only)
- fleetwood, holiday-rambler, travel-lite, american-coach, host, sunset-park, braxton-creek
- Needs: sitemap-based discovery or manual model URL list

### Coverage enrichment (2026-04-17)

Re-scraped 16 thin-coverage brands with tuned `brand_configs.py` entries
(`model_path_patterns`, tighter `listing_pages`, `force_playwright` where the
category page was SPA-rendered, `exclude_patterns` to skip `/features/`,
`/decor/`, `/brochure/`, `/design-options` duplicate pages). All writes went
through `INSERT OR IGNORE` so existing rows were preserved.

Delta for brands touched in this run:

| brand           | models         | floorplans     | images           |
|-----------------|----------------|----------------|------------------|
| highland-ridge  | 7 -> 12 (+5)   | 0 -> 34 (+34)  | 86 -> 144 (+58)  |
| drv             | 5 -> 7 (+2)    | 1 -> 1 (+0)    | 32 -> 32 (+0)    |
| happier-camper  | 11 -> 15 (+4)  | 8 -> 15 (+7)   | 28 -> 30 (+2)    |
| roadtrek        | 5 -> 14 (+9)   | 2 -> 20 (+18)  | 8 -> 8 (+0)      |
| airstream       | 39 -> 69 (+30) | 16 -> 33 (+17) | 20 -> 20 (+0)    |
| lance           | 22 -> 49 (+27) | 9 -> 51 (+42)  | 37 -> 112 (+75)  |
| newmar          | 14 -> 22 (+8)  | 7 -> 7 (+0)    | 0 -> 0 (+0)      |
| northwood       | 6 -> 18 (+12)  | 4 -> 79 (+75)  | 44 -> 89 (+45)   |
| taxa            | 3 -> 8 (+5)    | 2 -> 8 (+6)    | 40 -> 97 (+57)   |
| winnebago       | 22 -> 41 (+19) | 15 -> 26 (+11) | 161 -> 293 (+132)|
| jayco           | 25 -> 33 (+8)  | 21 -> 65 (+44) | 20 -> 20 (+0)    |
| pleasure-way    | 11 -> 16 (+5)  | 10 -> 20 (+10) | 100 -> 100 (+0)  |
| stealth         | 12 -> 17 (+5)  | 12 -> 19 (+7)  | 4 -> 85 (+81)    |
| work-and-play   | 6 -> 12 (+6)   | 6 -> 12 (+6)   | 4 -> 39 (+35)    |
| cedar-creek     | 8 -> 15 (+7)   | 8 -> 16 (+8)   | 9 -> 57 (+48)    |
| cardinal        | 11 -> 18 (+7)  | 11 -> 20 (+9)  | 14 -> 175 (+161) |

**Totals for this run: +159 models, +294 floorplans, +694 images.**

Brands that did not improve on this pass and need follow-up:
- **drv** -- `/brand/<slug>/` pages load JS-lazy floorplan carousels; Gemini
  sees the hero copy but not the individual floorplan specs. Consider
  `force_stealth` + higher `settle_ms`, or scrape the secondary
  `drvsuites.wpengine.com` host which mirrors the same content without lazy
  loading.
- **newmar** -- `/design-options` + `/floor-plans/<id>` sub-pages still get
  classified as models (Gemini returns the parent model name). The parent
  `/models/<slug>/` pages don't include per-floorplan spec blocks in their
  first-paint HTML even with Playwright. Needs per-floorplan URL seed list
  or a two-pass extractor (series page -> floorplan URLs -> spec scrape).

Runner: `scripts/enrich_coverage.py` (new). Reuses
`orchestrator.scrape_manufacturer`; concurrency capped at 3 so we don't
hammer Gemini / IPRoyal. DB backup at `data/rv_catalog.db.bak.20260417-1646`.

### Future
- Cloud Run deploy with production DB
- MCP server wrapper
- API auth for dealer sites
- Image storage on GCS
- Rate limiting, caching
