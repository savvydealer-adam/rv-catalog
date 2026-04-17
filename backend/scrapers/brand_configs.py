"""Per-brand scraping configuration overrides.

Most OEM sites work with the generic scraper (sitemap.xml -> model pages).
But some use unconventional URL structures that need specific guidance.
"""

from typing import TypedDict


class BrandConfig(TypedDict, total=False):
    # Seed URLs to crawl for model discovery (category/listing pages)
    listing_pages: list[str]
    # Explicit model-page URLs (skip discovery, feed these straight to _extract_model).
    # Use for SPA filter-UI sites where category pages don't expose anchor links to
    # individual models in their rendered HTML (e.g. Thor Motor Coach, Coachmen).
    # Relative paths are joined against site_root; absolute URLs are kept as-is.
    model_urls: list[str]
    # URL path patterns that indicate a model page (in addition to defaults)
    model_path_patterns: list[str]
    # URL path patterns to exclude (in addition to defaults)
    exclude_patterns: list[str]
    # Force Playwright rendering for this brand (JS-heavy site)
    force_playwright: bool
    # Force puppeteer-real-browser (WAF bypass, Cloudflare Turnstile, local PC only)
    force_stealth: bool
    # Allow model URLs on a different domain than base_url (e.g. sub-brand hosted on parent site)
    allow_external_domains: bool


CONFIGS: dict[str, BrandConfig] = {
    # Thor Motor Coach: Nuxt SPA. Category pages DO expose model hrefs once rendered
    # (/ace, /hurricane, etc.) but the link-card UI + aggressive client-side filtering
    # trip the AI classifier. Seed the 39 known model URLs directly (harvested
    # 2026-04-17 by walking Class A/B/C + camper-vans + diesel + sprinter + toy-hauler
    # category pages with puppeteer-real-browser). Update list when TMC launches/retires
    # a coach.
    "thor-motor-coach": {
        "model_urls": [
            "/ace", "/aria", "/axis",
            "/chateau", "/chateau-sprinter", "/compass",
            "/delano",
            "/echelon", "/echelon-sprinter",
            "/four-winds", "/four-winds-sprinter",
            "/gemini",
            "/hurricane",
            "/inception", "/inception-hd", "/indigo",
            "/luminate",
            "/magnitude-grand",
            "/omni-trail", "/outlaw-class-c", "/outlaw-wild-west",
            "/palazzo-gt", "/palladium", "/pasadena", "/pasadena-sv",
            "/quantum", "/quantum-sprinter",
            "/resonate", "/riviera", "/rize",
            "/sanctuary", "/scope", "/sequence",
            "/talavera", "/tellaro", "/tiburon", "/tranquility",
            "/vegas",
            "/windsport",
        ],
        "force_stealth": True,
    },
    # Winnebago: models at /motorhomes/<type>/<model>
    "winnebago": {
        "listing_pages": [
            "/motorhomes/class-a",
            "/motorhomes/class-b",
            "/motorhomes/class-c",
            "/touring-coaches",
            "/towables/travel-trailers",
            "/towables/fifth-wheels",
        ],
        "force_playwright": True,
    },
    # Heartland: WordPress site behind Cloudflare, categories at /rv-type/<cat>/,
    # sub-brand pages at /brand/<slug>/ (each sub-brand page lists its floorplans)
    "heartland": {
        "listing_pages": [
            "/rv-type/travel-trailers/",
            "/rv-type/fifth-wheels/",
            "/rv-type/toy-haulers/",
            "/all-brands/",
        ],
        "model_path_patterns": ["/brand/"],
        "force_stealth": True,
    },
    # Coachmen: each RV category page (/motorhomes, /travel-trailers, etc.) lists the
    # models as top-level slugs on coachmenrv.com, but the nav/filter chrome confuses
    # the AI classifier and httpx can't see the rendered links. Seed the model URLs
    # directly (harvested 2026-04-17 from /motorhomes, /travel-trailers, /fifth-wheels,
    # /toy-haulers, /destination-trailers, /camping-trailers via puppeteer-real-browser).
    # Includes all active Coachmen + Shasta series sold under Coachmen's umbrella.
    "coachmen": {
        "model_urls": [
            "/adrenaline",
            "/apex-nano", "/apex-ultra-lite",
            "/beyond", "/brookstone",
            "/catalina-destination-series", "/catalina-legacy-edition",
            "/catalina-summit-series-7", "/catalina-summit-series-8",
            "/catalina-trail-blazer",
            "/chaparral",
            "/clipper-rok", "/clipper-travel-trailers",
            "/concord", "/cross-trail",
            "/encore", "/entourage", "/euro",
            "/freedom-express-liberty-edition", "/freedom-express-select",
            "/freedom-express-ultra-lite",
            "/freelander",
            "/galleria",
            "/leprechaun",
            "/mirada",
            "/northern-spirit", "/northern-spirit-bijou",
            "/northern-spirit-dlx-&-compact", "/northern-spirit-se",
            "/nova",
            "/phoenix", "/pixel", "/prism", "/pursuit",
            "/shasta", "/shasta-i-5-edition-&-compact",
            "/sportscoach-rd", "/sportscoach-srs",
        ],
        "force_stealth": True,
    },
    # Forest River corporate: each division has its own subtree
    "forest-river": {
        "listing_pages": [
            "/rvs/travel-trailers",
            "/rvs/fifth-wheels",
            "/rvs/toy-haulers",
            "/rvs/motorhomes",
            "/rvs/destination-trailers",
            "/rvs/park-models",
        ],
    },
    # Keystone Arcadia etc are on keystonerv.com
    "keystone": {
        "listing_pages": [
            "/travel-trailers",
            "/fifth-wheels",
            "/toy-haulers",
            "/destination-trailers",
        ],
    },
    # Dutchmen: split by type
    "dutchmen": {
        "listing_pages": [
            "/travel-trailers",
            "/fifth-wheels",
            "/toy-haulers",
        ],
    },
    # Airstream: unique URL structure
    "airstream": {
        "listing_pages": [
            "/travel-trailers",
            "/touring-coaches",
        ],
        "force_playwright": True,
    },
    # Highland Ridge
    "highland-ridge": {
        "listing_pages": [
            "/open-range",
            "/olympia",
            "/mesa-ridge",
            "/open-range-light",
            "/roamer",
        ],
    },
    # Cherokee family — migrated off cherokeerv.com (now a campground site) to
    # Forest River. Only "Cherokee Black Label" has a live series page as of
    # 2026-04-17; grey-wolf / arctic-wolf / wolf-pup domains return 404. Scrape
    # the Black Label series page and pattern-match floorplan URLs.
    "cherokee-rv": {
        "listing_pages": ["/rvs/cherokee-black-label"],
        "model_path_patterns": ["/rvs/cherokee-black-label/"],
    },
    # Alliance RV
    "alliance": {
        "listing_pages": [
            "/our-rvs",
            "/paradigm",
            "/valor",
            "/avenue",
            "/delta",
        ],
    },
    # Brinkley RV
    "brinkley": {
        "listing_pages": [
            "/models",
            "/model-z",
            "/model-i",
            "/model-g",
        ],
    },
    # Fleetwood
    "fleetwood": {
        "listing_pages": [
            "/class-a-motorhomes",
            "/class-c-motorhomes",
        ],
        "force_playwright": True,
    },
    # Gulf Stream
    "gulf-stream": {
        "listing_pages": [
            "/rvs",
            "/travel-trailers",
            "/fifth-wheels",
            "/toy-haulers",
            "/motorhomes",
        ],
    },
    # Tiffin
    "tiffin": {
        "listing_pages": [
            "/diesel-motorhomes",
            "/gas-motorhomes",
            "/all-motorhomes",
        ],
    },
    # Crossroads RV
    "crossroads": {
        "listing_pages": [
            "/travel-trailers",
            "/fifth-wheels",
            "/redwood",
            "/cruiser",
            "/volante",
        ],
    },
    # --- Qwen3-proposed configs (reviewed 2026-04-16) -------------------------
    # Aliner
    "aliner": {
        "listing_pages": [
            "/all-campers",
            "/shape/a-frame-campers",
            "/shape/teardrop",
            "/size/small-campers",
            "/size/medium-campers",
            "/size/large-campers",
            "/series/scout",
            "/series/ranger",
            "/series/classic",
            "/series/expedition",
            "/series/evolution",
            "/series/ascape",
        ],
    },
    # Bigfoot Industries
    "bigfoot": {
        "listing_pages": [
            "/rvs",
            "/rvs/travel-trailers",
        ],
        "force_playwright": True,
    },
    # Bowlus
    "bowlus": {
        "listing_pages": [
            "/available-inventory",
            "/rivet",
            "/endless-highways",
        ],
    },
    # Coach House RV
    "coach-house": {
        "listing_pages": [
            "/all-rvs",
            "/new-rvs-for-sale",
            "/used-rvs-for-sale",
        ],
    },
    # Cruiser RV
    "cruiser-rv": {
        "listing_pages": [
            "/all-brands",
            "/find-your-rv",
            "/view-all-rvs",
            "/inventory",
        ],
    },
    # Dynamax
    "dynamax": {
        "listing_pages": [
            "/motorhomes",
        ],
        "force_playwright": True,
    },
    # EarthRoamer
    "earthroamer": {
        "listing_pages": [
            "/models-sx",
            "/sx-explore",
            "/ltx-explore",
        ],
        "force_playwright": True,
    },
    # East to West RV
    "east-to-west": {
        "listing_pages": [
            "/motorhomes",
            "/toy-haulers",
            "/fifth-wheels",
            "/travel-trailers",
        ],
        "force_playwright": True,
    },
    # Genesis Supreme RV
    "genesis-supreme": {
        "listing_pages": [
            "/genesis-bumper-pulls",
        ],
    },
    # Hiker Trailers
    "hiker": {
        "listing_pages": [
            "/product-category/ready-built-trailers",
            "/mid-range-trailers",
            "/mid-range-xl",
            "/extreme-off-road",
        ],
        "force_playwright": True,
    },
    # Leisure Travel Vans
    "leisure-travel": {
        "listing_pages": [
            "/products",
            "/past-models",
        ],
        "force_playwright": True,
    },
    # Northern Lite
    "northern-lite": {
        "listing_pages": [
            "/short-bed-truck-campers",
            "/long-bed-truck-campers",
            "/4-season-truck-campers",
        ],
    },
    # Northstar Campers
    "northstar": {
        "listing_pages": [
            "/hardwall-campers",
            "/pop-up-campers",
        ],
    },
    # Outdoors RV
    "outdoors-rv": {
        "listing_pages": [
            "/our-rvs",
            "/travel-trailers",
            "/1-2-ton-towable-line",
            "/fifth-wheels-2",
            "/toy-haulers-2",
        ],
    },
    # Prime Time Manufacturing
    "prime-time": {
        "listing_pages": [
            "/fifth-wheels",
            "/travel-trailers",
        ],
        "force_playwright": True,
    },
    # Scamp Trailers
    "scamp": {
        "listing_pages": [
            "/available-now",
            "/showroom",
            "/showroom/trailer-layouts",
            "/showroom/13-trailers",
            "/showroom/16-trailers",
            "/showroom/19-trailers",
        ],
        "force_playwright": True,
    },
    # Shasta RV
    "shasta": {
        "listing_pages": [
            "/motorhomes",
            "/toy-haulers",
            "/fifth-wheels",
            "/travel-trailers",
            "/destination-trailers",
            "/camping-trailers",
        ],
        "force_playwright": True,
    },
    # Storyteller Overland
    "storyteller": {
        "listing_pages": [
            "/pages/2026-mode-vans",
            "/pages/gxv-compare",
        ],
    },
    # --- Coverage enrichment configs (2026-04-17) ------------------------------
    # DRV Suites: WordPress /brand/<slug>/ series pages
    "drv": {
        "listing_pages": [
            "/brand/full-house-luxury-fifth-wheel-toy-haulers/",
            "/brand/mobile-suites-luxury-fifth-wheels/",
            "/brand/tradition/",
            "/brand/elite-suites/",
        ],
        "model_path_patterns": ["/brand/"],
    },
    # Highland Ridge: series pages listed, but floorplans live under
    # /rvs/<type>/<slug>/. Pattern-match those and force playwright for SPA cards.
    "highland-ridge": {
        "listing_pages": [
            "/open-range",
            "/olympia",
            "/mesa-ridge",
            "/open-range-light",
            "/roamer",
            "/roamer-light-duty",
            "/range-lite",
            "/open-range-3x",
        ],
        "model_path_patterns": ["/rvs/travel-trailers/", "/rvs/fifth-wheels/"],
        "force_playwright": True,
    },
    # Lance: /travel-trailers/<code>/ and /truck-campers/<code>/
    "lance": {
        "listing_pages": [
            "/travel-trailers",
            "/truck-campers",
        ],
        "model_path_patterns": ["/travel-trailers/", "/truck-campers/"],
        "exclude_patterns": ["/decor/", "/features/", "/gallery/"],
    },
    # Newmar: avoid design-options / sub-floorplan-id pages (duplicates)
    "newmar": {
        "listing_pages": [
            "/models",
            "/diesel-motorhomes",
            "/gas-motorhomes",
        ],
        "model_path_patterns": ["/models/"],
        "exclude_patterns": ["/design-options", "/floor-plans/", "/brochure"],
        "force_playwright": True,
    },
    # Jayco: individual model pages under /rvs/<type>/<slug>/
    "jayco": {
        "listing_pages": [
            "/rvs/travel-trailers",
            "/rvs/fifth-wheels",
            "/rvs/toy-haulers",
            "/rvs/class-a-motorhomes",
            "/rvs/class-c-motorhomes",
            "/rvs/camping-trailers",
        ],
        "model_path_patterns": ["/rvs/"],
        "force_playwright": True,
    },
    # Roadtrek: /models/<slug>/
    "roadtrek": {
        "listing_pages": [
            "/models",
            "/class-b-motorhomes",
        ],
        "model_path_patterns": ["/models/"],
    },
    # Pleasure-Way: /models/<slug>/
    "pleasure-way": {
        "listing_pages": [
            "/models",
        ],
        "model_path_patterns": ["/models/"],
    },
    # Northwood: /travel-trailers/<series>/<code>/ and /toy-haulers/<series>/<code>/
    "northwood": {
        "listing_pages": [
            "/travel-trailers",
            "/toy-haulers",
            "/fifth-wheels",
            "/arctic-fox",
            "/nash",
            "/desert-fox",
            "/wolf-creek",
        ],
        "model_path_patterns": ["/travel-trailers/", "/toy-haulers/", "/fifth-wheels/"],
    },
    # Happier Camper: Shopify /products/ — color variants pollute results
    "happier-camper": {
        "listing_pages": [
            "/collections/all",
            "/pages/hc1",
            "/pages/hct",
            "/pages/traveler",
        ],
        "model_path_patterns": ["/products/"],
    },
    # Taxa Outdoors: Shopify, has 3 real trailer products (cricket/mantis/woolly)
    "taxa": {
        "listing_pages": [
            "/collections/all",
            "/collections/trailers",
            "/pages/cricket",
            "/pages/mantis",
            "/pages/woolly-bear",
            "/pages/tigermoth",
        ],
        "model_path_patterns": ["/products/"],
    },
}


def get_config(slug: str) -> BrandConfig:
    return CONFIGS.get(slug, {})
