# RV Catalog -- Central RV Knowledge Base & API

## What This Is

A standalone service that owns all RV manufacturer, model, and floorplan data. Dealer websites (STL RV, future sites) call this API instead of maintaining their own knowledge bases. Includes an admin dashboard for monitoring coverage across 60+ manufacturers.

## Current State (2026-04-20, residual-cleanup round)

**Coverage:** 93 manufacturers seeded, **83 with scraped data (100% of active)**, **1,032 models, 2,410 floorplans, 11,331 images**.
(10 defunct: renegade, redwood, adventurer, regency, encore, cherokee-arctic-wolf, cherokee-grey-wolf, cherokee-wolf-pup, braxton-creek, sunset-park. **0 live brands still at 0 models.**)

**2026-04-20 deltas (residual follow-ups from the 04-17 PLAN.md list):**
- **newmar images**: 0 → **369** (+369). `_extract_image_urls` extended to accept extensionless CDN URLs (Scene7 `/is/image/`, Cloudinary `/image/upload/`, imgix, Shopify CDN) and HTML-decode `&amp;` in src attrs.
- **coachmen re-scrape**: 30 → 39 models, 135 → 293 floorplans (+158), 433 → 777 images (+344). The 9 previously-"null" seeds (apex-ultra-lite, catalina-summit-series-8, chaparral, cross-trail, freedom-express-ultra-lite, northern-spirit, northern-spirit-dlx-&-compact, shasta, shasta-i-5-edition-&-compact) all extract cleanly now — the 16k maxOutputTokens bump (c937e3d) had already fixed them; they just hadn't been re-run.
- **DB cleanup**: -29 junk rows across drv/grand-design/lance (/decor/, /features/, /find-model/, /archive, /test/, /adventure-more/, #acsbMenu, /wp-json/). Cascade-deleted orphan floorplans + images. Backup at `data/rv_catalog.db.bak.cleanup-20260418-150121`.
- **Spec-table prompt hint**: added explicit guidance for Gemini to parse `<table>/<dl>/<dt>/<dd>` spec blocks into `length_ft`/`sleeping_capacity`/`dry_weight_lbs`/`gvwr_lbs`/`slideout_count`/`bathroom_count` when the site renders them below the main text. Effect still-to-measure across re-scrape runs — on sampled pages where the spec isn't published (Airstream floorplan pages show Length only), the None values are genuine, not extractor misses.

**Session deltas (2026-04-17, single-day run):**
484 → 1,052 models (+568) · 842 → 2,264 floorplans (+1,422) · 3,111 → 10,666 images (+7,555) · 54 → 83 brands with data (+29).

**Key extractor fixes shipped this session (not just tuning):**
- `base.py` HTML truncation bumped 60 KB → **150 KB** + nav/header/footer stripped (floorplan rosters on content-heavy pages sit past 60 KB — Jayco Redhawk codes at ~117 KB, Airstream Classic at ~100 KB).
- Gemini `maxOutputTokens` 4096 → **16384** + truncation-repair fallback in `_parse_json` (Gemini 2.5 Flash burns 3,900+ tokens on thinking before JSON emit — smaller budgets silently dropped everything).
- `_rank_images()` scores images by model-name/URL-tail tokens with nav/menu/logo penalty before the 20-cap (prevents mega-menu chrome from starving real model photos).
- `_extract_image_urls` now reads `data-src`, `data-lazy-src`, and `<source srcset="">` (Airstream lazy-load pattern).
- Images `UNIQUE(source_url)` → **`UNIQUE(model_id, source_url)`** (shared floorplan CDN assets across sibling model pages were being dropped by `INSERT OR IGNORE`).
- `model_urls` short-circuit in `_discover_models` (skip listing + AI link classify; feed per-floorplan URLs directly) — used by thor-motor-coach, coachmen, airstream, winnebago, newmar, drv, and the Forest River sub-brands.

**Residual follow-ups (post-2026-04-20):**
- **Spec-table hit rate**: the prompt hint landed (commit 3ade128) but no brand was re-scraped to measure its effect. Next maintenance pass should re-run a sample (jayco, winnebago, tiffin) and diff `dry_weight_lbs`/`sleeping_capacity`/`slideout_count` completion rates.
- **Low-image active brands** (per `defunct=0`, `imgs<15`): bowlus, vengeance, travel-lite, sierra, hiker, sandpiper, surveyor, shasta, northern-lite, scamp, crossroads, xlr-toy-hauler, ember, palomino, roadtrek, flagstaff-rv. Some (bowlus, scamp) don't publish images; others (roadtrek, flagstaff-rv, ibex, sabre) are worth a re-scrape run now that the extractor is stricter about menu chrome.
- **IPRoyal blocking httpx-only OEM sites (2026-04-20 finding)**: when CD_IPROYAL_USER/PASS are set, the httpx path via IPRoyal rotating-residential returns empty/200 bodies for certain OEM sites (confirmed on ibexrvs.com — blank body; extraction returns None with zero errors). The 403-fallback to stealth_fetch only triggers on status codes, not on empty bodies. Affects any brand that lacks `force_stealth: True` + `model_urls` and relies on httpx+IPRoyal for page fetches. Fix path: make `_extract_model` treat HTML < 5KB from IPRoyal as "suspicious" and retry through stealth_fetch, or bypass proxy entirely for brands in a denylist. Workaround for single runs: `CD_IPROYAL_USER= CD_IPROYAL_PASS= python scripts/run_scraper.py --slug <x>`.

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
Knobs per entry: `listing_pages`, `model_urls`, `model_path_patterns`, `force_playwright`, `force_stealth`, `exclude_patterns`, `allow_external_domains`.

Hand-curated: thor-motor-coach (**model_urls + force_stealth**), winnebago, heartland (**force_stealth**), coachmen (**model_urls + force_stealth**), forest-river, keystone, dutchmen, airstream, highland-ridge, cherokee-rv, alliance, brinkley, fleetwood, gulf-stream, tiffin, crossroads.

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
- **thor-motor-coach, coachmen — RESOLVED 2026-04-17.** Option A (explicit model-URL
  seed lists) via a new `model_urls` field in `BrandConfig`. When set,
  `_discover_models` skips listing-page crawl + AI classification and feeds the URLs
  straight to `_extract_model` (each fetched via `force_stealth`).
  - thor-motor-coach: 0 → 38 models / 38 floorplans / 187 images (39 seed URLs
    harvested by walking Class A/B/C/camper-van/diesel/sprinter/toy-hauler category
    pages with puppeteer-real-browser; Nuxt hydrates `/ace`, `/hurricane`, etc.).
  - coachmen: 1 → 30 models / 135 floorplans / 433 images (38 seed URLs harvested
    from /motorhomes, /travel-trailers, /fifth-wheels, /toy-haulers,
    /destination-trailers, /camping-trailers).
  - `orchestrator.scrape_manufacturer` bumps `max_models` to `max(25, len(model_urls))`
    so the full seed list is scraped even when it exceeds the default cap.
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

### Sites with no category page (model-pages-only) -- RESOLVED 2026-04-17
All cracked via `model_urls` seed lists or `force_stealth` in `brand_configs.py`:
- fleetwood: `force_stealth` → 24 models / 77 floorplans / 480 images (Cloudflare WAF).
- holiday-rambler: generic discovery worked → 25 models / 80 floorplans / 500 images.
- american-coach: generic discovery worked → 6 models / 19 floorplans / 120 images.
- travel-lite: `/rvs/<slug>/` `model_urls` seed → 2 models / 6 floorplans / 2 images.
- host: `/product-details-<model>/` `model_urls` seed → 3 models / 3 floorplans / 24 images.
- sunset-park: **DEFUNCT 2026-04-17** — domain parked on atom.com (for sale).
- braxton-creek: **DEFUNCT 2026-04-17** — domain redirects to bontrageroutdoors.com (403).

### Forest River CMS platform brands -- RESOLVED 2026-04-17

Many OEM brands share a Forest River-owned CMS (same HTML layout, top-level
slugs as series pages, `/<series>/<model>/<id>` detail URLs). Added explicit
`model_urls` seeds in `brand_configs.py`:

- east-to-west: 13 series seeded → 9 models / 46 floorplans / 170 images.
- prime-time: 5 series seeded → 5 models / 31 floorplans / 99 images.
- dynamax: 8 series seeded → 7 models / 22 floorplans / 139 images.
- cruiser-rv: 6 `/brand/<slug>/` seeds → 5 models / 2 floorplans / 100 images.
- coach-house: 10 `/<model>/` seeds → 10 models / 15 floorplans / 185 images.
- northstar: 12 `/<model>/` seeds → 11 models / 11 floorplans / 208 images.
- genesis-supreme: 16 `/<series>-new/` seeds → 15 models / 23 floorplans / 300 images.
- storyteller: 13 `/pages/<van>` seeds → 11 models / 25 floorplans / 220 images.

### Forest River sub-brand URL corrections (2026-04-17)

DB URLs for 5 FR sub-brands pointed at `/rvs/<category>/<brand>` paths that
now 404. Fixed to the live `/rvs/<brand>` format:
- forester: 0 → 10 models / 12 floorplans / 118 images.
- sunseeker: 0 → 10 models / 12 floorplans / 146 images.
- georgetown: 0 → 3 models / 11 floorplans / 57 images.
- solera: 0 → 12 models / 12 floorplans / 100 images.
- fr3: 0 → 4 models / 4 floorplans / 59 images.
- salem-rv: re-pointed to `/rvs/salem` → 11 models / 11 floorplans / 188 images.

### Forest River parent brand (2026-04-17)

Added 51 umbrella-brand series slugs as `model_urls` (those not already in
individual brand records): 20 models / 142 floorplans / 398 images.

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

Runner: `scripts/enrich_coverage.py` (new). Reuses
`orchestrator.scrape_manufacturer`; concurrency capped at 3 so we don't
hammer Gemini / IPRoyal. DB backup at `data/rv_catalog.db.bak.20260417-1646`.

### newmar + drv follow-up (2026-04-17, round 3)

Both thin brands cracked via explicit `model_urls` seeds — same pattern as
thor-motor-coach / coachmen. Lazy-loaded floorplan carousels on the parent
series pages were never going to surface specs to Gemini, so we skip them
entirely and feed per-floorplan URLs straight to `_extract_model`.

- **newmar**: harvested 65 `/models/<slug>/2026-<slug>/floor-plans/<code>`
  URLs across all 16 active 2026 coaches via `scripts/harvest_newmar_floorplans.py`
  (walks each series page under stealth, regex-grabs `/floor-plans/\d+` hrefs).
  Seeded those URLs + `force_stealth: True` in `brand_configs.py`.
  Before: 22 models / 7 floorplans / 0 images.
  After:  **23 models / 69 floorplans / 0 images (+62 fp).**
  Gemini groups multiple floorplan URLs under the same parent series (Dutch
  Star → 8 fp, Super Star → 7 fp, Bay Star → 7 fp, Essex → 4 fp, etc.) via
  `INSERT OR IGNORE`, so the row count stays bounded while the floorplan
  count climbs. Zero images: Newmar serves `<img src="">` without extensions
  (CDN/dynamic URLs), so `_extract_image_urls` filters them out.
- **drv**: `/brand/<slug>/` series pages lazy-load floorplan cards (no anchor
  hrefs in server HTML even under stealth, confirmed by grepping the 687 KB
  rendered output). Per-floorplan pages live at `/rv-model/<code>/` and were
  fully harvestable from `drvsuites.com/rv-model-sitemap.xml` (Yoast). Seeded
  14 live `/rv-model/` URLs + `force_stealth: True`. Each page contains one
  floorplan with real dry-weight / GVWR / slides / bedroom specs.
  Before: 7 models / 1 floorplan / 32 images.
  After:  **19 models / 12 floorplans / 272 images (+11 fp, +240 img).**

Both fixes are same-shape as existing `model_urls` configs; no base.py
changes required. DB backup at `data/rv_catalog.db.bak.newmar-drv-20260417-1932`.

### Round 2 extractor fix (2026-04-17)

Three high-traffic brands -- **airstream, winnebago, jayco** -- were carrying
most of their rows with 0 floorplans AND 0 images despite working fetches.
Two root causes, both in `base.py _extract_model`:

1. **60 KB truncation ate the floorplan section.** Gemini only saw the first
   60 KB of cleaned HTML. On content-heavy model pages the floorplan roster
   sits at ~100-120 KB (Jayco Redhawk codes 24B/26M/29XK/31F at offset 117 KB,
   Airstream Classic `33FB` at ~100 KB). Bumped truncation to **150 KB** and
   added `<nav>/<header>/<footer>` stripping so mega-menu chrome no longer
   consumes the budget.
2. **Images sliced at 20 after DOM order.** `image_urls[:20]` kept the first
   20 images encountered, which on every site tested were menu/nav chrome.
   Added `_rank_images()` that scores images by how many tokens they share
   with the model name + URL-path tail (boost) and how many nav/logo/menu
   keywords they contain (penalty), then sorts before the 20-cap. Also
   expanded `_extract_image_urls` to pick up `data-src`, `data-lazy-src`,
   and `<source srcset="">` (needed for Airstream's lazy-load pattern).

Plus per-brand tuning in `brand_configs.py`:

- **airstream**: Pure `model_urls` seeds (22 model pages + 18 `/floorplans/`
  index pages). The `/floorplans/` indexes carry the full code roster; the
  model-root pages carry hero/lifestyle images. Seeding explicit URLs skips
  the junk sub-pages (`/features/`, `/specifications/`, `/brochure/`,
  `/brochure/thank-you/`, `/floorplans/<code>/`) that the Gemini link
  classifier was marking as model pages and was creating N dup rows per
  model with NULL model_year (bypassing the `UNIQUE` constraint).
- **winnebago**: `model_urls` = 33 canonical `/models/<slug>` harvested from
  sitemap. Old config crawled listing pages which returned BOTH
  `/models/<slug>` and `/models/product/<cat>/<sub>/<slug>` -- the `product/`
  legacy route is a thin hub. `exclude_patterns: ["/models/product/"]` as
  belt-and-suspenders.
- **jayco**: Left `listing_pages` + `model_path_patterns: ["/rvs/"]`
  unchanged but added `exclude_patterns` for `/floorplans/`, `/brochure`,
  `/features`, `/specifications`, `/standard-features`, `/options` so
  Gemini doesn't treat those sub-pages as new models. The 150 KB
  truncation bump is load-bearing here (Redhawk floorplan section is at
  117 KB).

Post-run dedup script deleted empty rows that shared `source_url` with a
populated row (legacy dupes from pre-fix scrapes that had NULL `model_year`)
+ one stale Jayco row whose URL now 301-redirects (Redhawk slug migrated to
Redhawk SE).

Before/after (each brand's manufacturer counters):

| brand      | models         | floorplans      | images           | empty rows |
|------------|----------------|-----------------|------------------|------------|
| airstream  | 69 -> 47       | 33 -> **85**    | 20 -> **665**    | 39 -> 0    |
| winnebago  | 41 -> 59       | 26 -> **59**    | 293 -> **503**   | 11+ -> 0   |
| jayco      | 33 -> 35       | 65 -> **90**    | 20 -> **641**    | 17+ -> 0   |

**Totals: +117 floorplans, +1,476 images, -67 junk rows across the three.**

Airstream model count *dropped* because the old 69 was inflated with 39
dup/junk rows (each sub-page getting its own NULL-year row); the 47 we end
at is the real roster (16 travel-trailers + 6 touring coaches, each
represented once by a populated canonical row and once by a populated
`/floorplans/` row that persist merges via model_name). Winnebago model
count went up because the seed list surfaced canonical pages the old
listing crawl missed (sunflyer, horizon, hike-100, m-series, etc).

DB backup at `data/rv_catalog.db.bak.round2-20260417-1926`.

### Round 2 image backfill (2026-04-17)

Four more brands -- **holiday-rambler, fleetwood, grand-design, lance** --
had good floorplan coverage but most models showed 0 images in the DB
(holiday-rambler 24/25 rows at 0 imgs, fleetwood 23/24, grand-design 23/36,
lance 22/49). Root-cause analysis turned up three independent bugs that
compounded:

1. **Gemini 2.5 Flash MAX_TOKENS truncation.** `maxOutputTokens: 4096`
   wasn't enough: the model burns most of that budget on internal
   "thinking" tokens (3900+ per request observed) before emitting JSON, so
   responses with 6+ floorplans got cut off mid-string. `_parse_json`
   returned None, which made `_extract_model` return None, which prevented
   any persist -- no model, no floorplans, no images. **Fix:** bumped to
   `maxOutputTokens: 16384` AND added a truncation-repair path in
   `_parse_json` that walks back to the last valid cut point and closes
   open braces/brackets so a partial response still yields usable data.
2. **`UNIQUE(source_url)` blocked shared floorplan images.** Grand Design's
   parent series pages (e.g. `/fifth-wheels/reflection`) and sub-model
   pages (`/fifth-wheels/reflection/303rls`) both link to the same
   `303RLS.png` CDN asset. Whichever model got scraped first claimed the
   URL; every other model hit `INSERT OR IGNORE` and silently dropped.
   **Fix:** migrated the constraint to `UNIQUE(model_id, source_url)` so
   the same image URL can be associated with multiple models legitimately.
   Applied in-place to the running DB and updated `database.py` SCHEMA_SQL.
3. **Holiday Rambler was WAF-blocked on httpx.** holidayrambler.com
   returned 403 to every httpx request even through IPRoyal. The 403
   fallback path to stealth_fetch sometimes failed due to the default 60 s
   nav timeout. **Fix:** added `holiday-rambler` to `brand_configs.py`
   with `force_stealth: True`, matching the fleetwood config.

Fleetwood, holiday-rambler, and most of the other zero-image failures were
actually caused by the image-ranker work-stealing: the first model scraped
on a page would grab 20 sibling-thumbnail URLs from the "Check out our
other models" rail (Palisade, Discovery, Frontier, etc -- all present on
every Fleetwood model page), and the `UNIQUE(source_url)` constraint then
blocked every subsequent model from storing the same URLs. Fix #2 alone
would have helped, but the round-2 `_rank_images` (committed in c937e3d)
also ensures each model claims its own hero/gallery URLs first.

Before/after (each brand's manufacturer counters):

| brand            | models     | floorplans    | images         | zero-image rows |
|------------------|------------|---------------|----------------|-----------------|
| holiday-rambler  | 25 -> 26   | 80 -> 84      | 20 -> **518**  | 24 -> 1         |
| fleetwood        | 24 -> 31   | 77 -> 101     | 20 -> **614**  | 23 -> 1         |
| grand-design     | 36 -> 90   | 73 -> 135     | 93 -> **647**  | 23 -> 10        |
| lance            | 49 -> 57   | 51 -> 72      | 112 -> **466** | 22 -> 18        |

**Totals: +2,000 images across the four brands.**

Remaining zero-image rows are pre-existing dedup artifacts -- multiple
model rows share a source_url but have slightly different `model_name`
values from earlier scrape-AI variations (e.g. `"324MBS"` vs
`"Reflection 324MBS"` for the same page). The populated row is the newer
one; the legacy row is defunct. Lance's 18 stale rows are all
`/decor/`, `/features/`, and `/find-model/` sub-pages that should have
been excluded by the current config (which does have the exclude) but
were persisted before the exclude was added.

DB backup at `data/rv_catalog.db.bak.imgfill-20260417-1933`.

### Future
- Cloud Run deploy with production DB
- MCP server wrapper
- API auth for dealer sites
- Image storage on GCS
- Rate limiting, caching
