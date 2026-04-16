# RV Catalog -- Central RV Knowledge Base & API

## What This Is

A standalone service that owns all RV manufacturer, model, and floorplan data. Dealer websites (STL RV, future sites) call this API instead of maintaining their own knowledge bases. Includes an admin dashboard for monitoring coverage across 60+ manufacturers.

## Architecture

```
rv-catalog/
  backend/          FastAPI REST API + scraping pipeline
    routers/        API route modules
    scrapers/       Per-manufacturer scraper modules
  dashboard/        React/Vite admin dashboard (coverage monitor)
  mcp/              MCP server wrapper (for Claude Code access)
  data/             SQLite databases
  scripts/          Seed scripts, migration tools
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

## Dashboard Pages

1. **Overview** -- Total manufacturers, models, floorplans. Coverage % by tier.
2. **Manufacturer Grid** -- Card per manufacturer with status badge (complete/partial/missing), model count, floorplan count, last scraped date.
3. **Manufacturer Detail** -- Drill into models/floorplans, data quality per field, missing data highlighted.
4. **Scrape Queue** -- Running/queued/failed scrape jobs. Trigger manual re-scrapes.
5. **Data Quality** -- Field-level completeness (% of floorplans with length, MSRP, sleeping cap, etc.)

## Database Schema

Extends the existing `rv_knowledge_base.db` from rv-research with:

### New/Modified Tables

```sql
-- Extended manufacturer table
manufacturers:
  + tier              TEXT     -- "1_flagship", "2_secondary", "3_midtier", "4_independent"
  + parent_company_id INTEGER -- self-referential for brand grouping
  + rvia_member       BOOLEAN
  + market_share_pct  REAL
  + scrape_status     TEXT     -- "not_started", "in_progress", "partial", "complete"
  + scrape_priority   INTEGER  -- 1=highest
  + last_scraped_at   TEXT
  + model_count       INTEGER  -- denormalized for dashboard speed
  + floorplan_count   INTEGER
  + coverage_pct      REAL     -- calculated field

-- Scrape tracking
scrape_runs:
  id, manufacturer_id, started_at, finished_at,
  status (running/success/partial/error),
  models_found, models_added, floorplans_found, floorplans_added,
  errors TEXT (JSON array), duration_s

-- Parent companies (Thor Industries, Berkshire Hathaway, etc.)
parent_companies:
  id, name, market_share_pct, brand_count, website
```

Existing tables (models, floorplans, images) stay as-is -- the schema is solid.

---

## Manufacturer Scraping Plan

### Priority Tiers & Waves

Coverage target: **65+ manufacturers, 500+ models, 3000+ floorplans**

The US RV market is controlled by 4 parent companies (~92% market share).
We scrape their brands in priority order based on unit volume.

---

### WAVE 1 -- Big 8 Flagships (~70% of market)
*Target: 8 brands, ~200 models, ~1200 floorplans*

| # | Brand | Parent | Type | Website | Est. Models |
|---|-------|--------|------|---------|------------|
| 1 | Keystone RV | Thor | Towables | keystonerv.com | 25+ |
| 2 | Forest River | Berkshire | All | forestriverinc.com | 30+ |
| 3 | Jayco | Thor | All | jayco.com | 25+ |
| 4 | Grand Design | Winnebago | Towables | granddesignrv.com | 8+ |
| 5 | Heartland RV | Thor | Towables | heartlandrvs.com | 15+ |
| 6 | Coachmen RV | Berkshire | All | coachmenrv.com | 15+ |
| 7 | Winnebago | Winnebago | All | winnebago.com | 20+ |
| 8 | Thor Motor Coach | Thor | Motorized | thormotorcoach.com | 15+ |

### WAVE 2 -- Major Secondary Brands (~15% additional)
*Target: 9 brands, ~120 models, ~700 floorplans*

| # | Brand | Parent | Type | Website | Est. Models |
|---|-------|--------|------|---------|------------|
| 9 | Dutchmen | Thor | Towables | dutchmen.com | 12+ |
| 10 | Prime Time | Berkshire | Towables | primetimerv.com | 10+ |
| 11 | Palomino | Berkshire | Towables | palominorv.com | 10+ |
| 12 | KZ RV | Thor | Towables | kz-rv.com | 12+ |
| 13 | Airstream | Thor | All | airstream.com | 10+ |
| 14 | Highland Ridge | Thor | Towables | highlandridgerv.com | 8+ |
| 15 | Fleetwood RV | REV | Motorized | fleetwoodrv.com | 10+ |
| 16 | Holiday Rambler | REV | Motorized | holidayrambler.com | 6+ |
| 17 | Gulf Stream | Independent | All | gulfstreamcoach.com | 20+ |

### WAVE 3 -- Mid-Tier & Growing Brands (~7% additional)
*Target: 11 brands, ~80 models, ~500 floorplans*

| # | Brand | Parent | Type | Website |
|---|-------|--------|------|---------|
| 18 | Shasta | Berkshire | Towables | shastarving.com |
| 19 | East to West | Berkshire | Towables | easttowestrv.com |
| 20 | Starcraft | Thor | Towables | starcraftrv.com |
| 21 | Entegra Coach | Thor | Luxury Motor | entegracoach.com |
| 22 | Tiffin | Thor | Luxury Motor | tiffinmotorhomes.com |
| 23 | Newmar | Winnebago | Luxury Motor | newmarcorp.com |
| 24 | Crossroads RV | Thor | Towables | crossroadsrv.com |
| 25 | Alliance RV | Independent | Towables | alliancerv.com |
| 26 | Brinkley RV | Independent | Towables | brinkleyrv.com |
| 27 | Dynamax | Berkshire | Super C | dynamaxcorp.com |
| 28 | Lance Camper | Independent | TC, TT | lancecamper.com |

### WAVE 4 -- Long Tail Independents
*Target: 30+ brands, ~100 models, ~400 floorplans*

| # | Brand | Type | Website |
|---|-------|------|---------|
| 29 | Northwood Mfg | TT, 5W | northwoodmfg.com |
| 30 | Ember RV | TT | emberrv.com |
| 31 | inTech RV | TT, TH | intechrv.com |
| 32 | nuCamp RV | TT | nucamprv.com |
| 33 | Outdoors RV | TT, 5W | outdoorsrvmfg.com |
| 34 | Pleasure-Way | Class B | pleasureway.com |
| 35 | Leisure Travel Vans | Class B | leisurevans.com |
| 36 | Cruiser RV | Towables | cruiserrv.com |
| 37 | DRV Luxury Suites | 5W | drvsuites.com |
| 38 | Venture RV | Towables | venture-rv.com |
| 39 | Oliver Travel Trailers | TT | olivertraveltrailers.com |
| 40 | Travel Lite | TT, TC | travelliterv.com |
| 41 | Coach House | Class B/C | coachhouserv.com |
| 42 | Roadtrek | Class B | roadtrek.com |
| 43 | American Coach | Luxury A | americancoach.com |
| 44 | Renegade RV | Super C | raborv.com |
| 45 | Midwest Auto Designs | Class B | midwestautomotivedesigns.com |
| 46 | Aliner | A-Frame | aliner.com |
| 47 | Scamp | Small TT | scamptrailers.com |
| 48 | Casita | Fiberglass TT | casitatraveltrailers.com |
| 49 | Bowlus | Premium TT | bowlus.com |
| 50 | Northern Lite | TC | northern-lite.com |
| 51 | Northstar Campers | TC | northstarcampers.com |
| 52 | Bigfoot Industries | TC, TT | bigfootrv.com |
| 53 | Host Campers | TC | hostcampers.com |
| 54 | EarthRoamer | Expedition | earthroamer.com |
| 55 | Hiker Trailers | Teardrop | hikertrailers.com |
| 56 | Storyteller Overland | Class B | storytelleroverland.com |
| 57 | Redwood RV | Luxury 5W | redwood-rv.com |
| 58 | Genesis Supreme | TH | genesissupreme.com |
| 59 | Sunset Park RV | TT | sunsetparkrv.com |
| 60 | Braxton Creek | TT | braxtoncreek.com |
| 61 | Taxa Outdoors | TT | taxaoutdoors.com |
| 62 | Happier Camper | Small TT | happiercamper.com |
| 63+ | Remaining niche brands | Various | Various |

---

## Scraping Strategy Per Manufacturer

Most OEM sites follow one of these patterns:

### Pattern A: Model Gallery Page
`/models` or `/rvs` -> list of model lines -> each has floorplan subpages
**Examples:** Keystone, Jayco, Grand Design, Winnebago

### Pattern B: Product Configurator
Interactive tool with specs/pricing per floorplan
**Examples:** Airstream, some luxury brands

### Pattern C: PDF Brochure Only
Specs only in downloadable PDFs (need PDF parsing)
**Examples:** Some smaller independents

### Scraper Architecture
```python
# Base scraper class
class OEMScraper:
    manufacturer_slug: str
    base_url: str

    async def discover_models(self) -> list[RawModel]
    async def scrape_model(self, url: str) -> ModelDetail
    async def scrape_floorplan(self, url: str) -> FloorplanDetail
    async def download_images(self, model_id: int) -> list[Image]

# Per-manufacturer implementations
class KeystoneScraper(OEMScraper): ...
class ForestRiverScraper(OEMScraper): ...
# etc.
```

Each scraper:
1. Discovers all current-year models from the OEM site
2. Extracts specs per model and per floorplan
3. Downloads floorplan drawings and hero images
4. Stores structured data in the knowledge base
5. Logs scrape status for dashboard

## Implementation Phases

### Phase 1: Foundation (this session)
- [x] Project scaffold
- [ ] Database schema (migrate + extend rv_knowledge_base.db)
- [ ] Seed 65+ manufacturers with priority/tier/parent company
- [ ] FastAPI with core read endpoints
- [ ] Dashboard: overview + manufacturer grid
- [ ] Deploy to Cloud Run

### Phase 2: Scraping Pipeline
- [ ] Base scraper class + Playwright integration
- [ ] Wave 1 scrapers (8 brands)
- [ ] Image download + GCS storage
- [ ] Scrape status tracking + dashboard integration

### Phase 3: Wave 2-3 Scraping
- [ ] Wave 2 scrapers (9 brands)
- [ ] Wave 3 scrapers (11 brands)
- [ ] Data quality scoring
- [ ] API: enrichment endpoint for dealer sites

### Phase 4: Full Coverage + Polish
- [ ] Wave 4 scrapers (30+ brands)
- [ ] Used RV data (depreciation, known issues)
- [ ] MCP server wrapper
- [ ] API auth for dealer sites
- [ ] Rate limiting, caching

## Known Scraping Blockers (2026-04-16)

**WAF-blocked (403 from Cloudflare/Akamai, residential IP doesn't help):**
- heartland, cherokee-rv + all Cherokee sub-brands (arctic-wolf, grey-wolf, wolf-pup)
- Needs: bot-header stack (Sec-Fetch headers, proper TLS fingerprint), not just IP rotation

**SPA filter-UI sites (category pages load, but model cards behind JS filter):**
- thor-motor-coach, winnebago, coachmen (existing configs point at category pages —
  `_ai_find_model_links` returns sibling categories instead of actual models)
- Needs: per-brand click-through or explicit model-URL lists in `brand_configs.py`

**Dead / unreliable origin servers:**
- adventurermfg.com, encorerv.com, redwood-rv.com, raborv.com (renegade): 504 gateway timeout
- regencyrv.com: expired SSL cert
- Action: verify domains still exist, mark as defunct or find alternate URL

**No category page, individual model pages only:**
- fleetwood, holiday-rambler, travel-lite, american-coach, host, sunset-park, braxton-creek
- Needs: sitemap-based discovery (strategy 2 in base.py), or manual model URL list
