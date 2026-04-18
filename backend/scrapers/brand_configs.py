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
    # Winnebago: models live at /models/<slug> OR /models/product/<cat>/<sub>/<slug>.
    # Listing-page discovery used to return BOTH which duplicated every model and
    # left many rows with 0 fp/img (the hub /models/<slug> version is often a
    # year-landing page). Seed the canonical /models/<slug> URLs harvested from
    # sitemap.xml 2026-04-17, skipping the /models/product/ legacy routes.
    "winnebago": {
        "model_urls": [
            "/models/adventurer",
            "/models/ekko",
            "/models/ekko-sprinter",
            "/models/era",
            "/models/forza",
            "/models/horizon",
            "/models/hike-100",
            "/models/intent",
            "/models/journey",
            "/models/micro-minnie",
            "/models/micro-minnie-fl",
            "/models/minnie",
            "/models/minnie-drop",
            "/models/minnie-plus",
            "/models/minnie-winnie",
            "/models/m-series",
            "/models/navion",
            "/models/outlook",
            "/models/revel",
            "/models/solis",
            "/models/solis-46",
            "/models/solis-pocket",
            "/models/spirit",
            "/models/sunflyer",
            "/models/sunstar",
            "/models/sunstar-npf",
            "/models/thrive",
            "/models/travato",
            "/models/view",
            "/models/view-navion",
            "/models/vista",
            "/models/vista-npf",
            "/models/voyage",
        ],
        "force_playwright": True,
        "exclude_patterns": ["/models/product/"],
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
        ],
        "model_path_patterns": ["/rvs/"],
        # Seed top umbrella-brand series (those without their own mfr record).
        "model_urls": [
            "/rvs/airelume", "/rvs/alpha-wolf", "/rvs/arctic-wolf",
            "/rvs/aurora", "/rvs/berkshire", "/rvs/cardinal",
            "/rvs/cascade", "/rvs/cedar-creek", "/rvs/cherokee-black-label",
            "/rvs/columbus", "/rvs/cruise-lite", "/rvs/evo",
            "/rvs/flagstaff-classic-travel-trailers", "/rvs/flagstaff-e-pro",
            "/rvs/flagstaff-micro-lite", "/rvs/flagstaff-shamrock",
            "/rvs/flagstaff-super-lite-travel-trailers",
            "/rvs/grand-surveyor", "/rvs/grey-wolf", "/rvs/hemisphere-travel-trailers",
            "/rvs/heritage-glen-travel-trailers", "/rvs/ibex",
            "/rvs/impression", "/rvs/lost-pines", "/rvs/nightfall",
            "/rvs/no-boundaries", "/rvs/ozark", "/rvs/puma", "/rvs/r-pod",
            "/rvs/riverstone", "/rvs/rockwood-geo-pro", "/rvs/rockwood-mini-lite",
            "/rvs/rockwood-signature-travel-trailers", "/rvs/sabre",
            "/rvs/sandpiper-fifth-wheels", "/rvs/sandstorm",
            "/rvs/sierra-fifth-wheels", "/rvs/solaire", "/rvs/stealth",
            "/rvs/timberwolf", "/rvs/vengeance", "/rvs/vibe",
            "/rvs/viking-travel-trailers", "/rvs/wildcat-travel-trailers",
            "/rvs/wolf-pack", "/rvs/wolf-pup", "/rvs/work-and-play",
            "/rvs/x-lite", "/rvs/xlr-boost", "/rvs/xlr-hyperlite",
            "/rvs/xlr-nitro",
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
    # Airstream: each model has /travel-trailers/<slug>/ canonical + N sub-pages
    # (/features/, /specifications/, /floorplans/, /floorplans/<code>/,
    # /brochure/, /brochure/thank-you/). The main model page exposes only
    # hero/lifestyle images — the /floorplans/ index page is the authoritative
    # source of floorplan codes. Seed BOTH for each model so the extractor
    # captures images from the main page AND the floorplan roster from the
    # /floorplans/ index (persist merges under the same model_name key).
    # Skipping sitemap discovery avoids the dup-sub-page explosion that left
    # 39 empty rows after round 1.
    "airstream": {
        "model_urls": [
            # Travel trailers — canonical model page + floorplan roster
            "/travel-trailers/classic/",
            "/travel-trailers/classic/floorplans/",
            "/travel-trailers/flying-cloud/",
            "/travel-trailers/flying-cloud/floorplans/",
            "/travel-trailers/globetrotter/",
            "/travel-trailers/globetrotter/floorplans/",
            "/travel-trailers/international/",
            "/travel-trailers/international/floorplans/",
            "/travel-trailers/international-signature/",
            "/travel-trailers/international-signature/floorplans/",
            "/travel-trailers/caravel/",
            "/travel-trailers/caravel/floorplans/",
            "/travel-trailers/bambi/",
            "/travel-trailers/bambi/floorplans/",
            "/travel-trailers/sport/",
            "/travel-trailers/sport/floorplans/",
            "/travel-trailers/basecamp/",
            "/travel-trailers/basecamp/floorplans/",
            "/travel-trailers/trade-wind/",
            "/travel-trailers/trade-wind/floorplans/",
            "/travel-trailers/nest/",
            "/travel-trailers/silver-lining/",
            "/travel-trailers/pottery-barn-special-edition/",
            "/travel-trailers/rei-special-edition/",
            "/travel-trailers/stetson-6666-special-edition/",
            "/travel-trailers/frank-lloyd-wright-special-edition/",
            # Touring coaches (Class B)
            "/touring-coaches/interstate-19gtx/",
            "/touring-coaches/interstate-19gtx/floorplans/",
            "/touring-coaches/interstate-24gt/",
            "/touring-coaches/interstate-24gt/floorplans/",
            "/touring-coaches/interstate-24glx/",
            "/touring-coaches/interstate-24glx/floorplans/",
            "/touring-coaches/interstate-24x/",
            "/touring-coaches/interstate-24x/floorplans/",
            "/touring-coaches/atlas/",
            "/touring-coaches/rangeline/",
        ],
        "force_stealth": True,
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
        "force_stealth": True,
    },
    # Holiday Rambler: Akamai-style WAF returns 403 on plain httpx even with
    # IPRoyal residential proxy. Forces stealth (puppeteer-real-browser) for
    # both listing + model pages. Confirmed 2026-04-17.
    "holiday-rambler": {
        "listing_pages": [
            "/class-a-motorhomes",
            "/class-c-motorhomes",
        ],
        "force_stealth": True,
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
    # Coach House RV (WP site, models at root slugs like /platinum/, /arriva/)
    "coach-house": {
        "listing_pages": [
            "/all-rvs/",
            "/new-rvs-for-sale/",
        ],
        "model_urls": [
            "/arriva/", "/platinum/", "/platinum-2/", "/platinum-3/",
            "/platinum-4/", "/platinum-261-iv/", "/platinum-271-iv/",
            "/platinum-272-iv/", "/platinum2-240/", "/platinum2-241xl/",
        ],
    },
    # Cruiser RV (brand pages live under /brand/<slug>/)
    "cruiser-rv": {
        "listing_pages": [
            "/all-brands/",
            "/find-your-rv/",
            "/view-all-rvs/",
        ],
        "model_path_patterns": ["/brand/"],
        "model_urls": [
            "/brand/avenir/", "/brand/embrace/", "/brand/essence/",
            "/brand/mpg/", "/brand/shadow-cruiser/", "/brand/stryker/",
        ],
    },
    # Dynamax (Forest River CMS, series pages at top-level slugs)
    "dynamax": {
        "listing_pages": [
            "/motorhomes",
        ],
        "model_urls": [
            "/dx3", "/dynaquest-xl", "/europa", "/europa-s", "/grand-sport",
            "/isata-3", "/isata-5", "/isata-6",
        ],
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
    # East to West RV (Forest River CMS, series pages at top-level slugs)
    "east-to-west": {
        "listing_pages": [
            "/motorhomes",
            "/toy-haulers",
            "/fifth-wheels",
            "/travel-trailers",
        ],
        "model_urls": [
            "/acclaim", "/ahara", "/alita", "/alta", "/blackthorn",
            "/bravado", "/college-avenue", "/della-terra", "/entrada",
            "/entrada-m-class", "/longitude", "/takoda", "/tandara",
        ],
    },
    # Genesis Supreme RV (WP site, many model lines at root slugs)
    "genesis-supreme": {
        "listing_pages": [
            "/genesis-bumper-pulls/",
        ],
        "model_urls": [
            "/blazen-fifth-wheel-new/",
            "/blazen-toyhauler-trailers-new/",
            "/genesis-fifth-wheels-new/",
            "/genesis-toyhauler-trailers-new/",
            "/mgm-fifth-wheels-new/",
            "/mgm-toyhauler-trailers-new/",
            "/northland-limited-new/",
            "/overnighter-toyhauler-trailers-new/",
            "/ragen-fifth-wheels-new/",
            "/ragen-toyhauler-trailers-new/",
            "/sandsport-fifth-wheels-new/",
            "/sandsport-toyhauler-trailers-new/",
            "/seabreeze-limited-new/",
            "/surfside-limited-new/",
            "/vortex-fifth-wheels-new/",
            "/vortex-toyhauler-trailers-new/",
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
    # Northstar Campers (WP site, all camper models at root slugs)
    "northstar": {
        "listing_pages": [
            "/hardwall-campers/",
            "/pop-up-campers/",
        ],
        "model_urls": [
            "/10-x/", "/600ss/", "/650sc/", "/850sc/", "/gmax-600/",
            "/gmax-650/", "/laredo-sc/", "/liberty/", "/night-hawk/",
            "/offroada/", "/tc650/", "/wind-bandit/",
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
    # Prime Time Manufacturing (Forest River CMS, series pages at top-level slugs)
    "prime-time": {
        "listing_pages": [
            "/fifth-wheels",
            "/travel-trailers",
        ],
        "model_urls": [
            "/avenger", "/crusader", "/lacrosse", "/sanibel", "/tracer",
        ],
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
    # DRV Suites: WordPress. Per-floorplan pages live at /rv-model/<code>/ but the
    # /brand/<slug>/ series pages lazy-load floorplan cards (no anchor hrefs in
    # server HTML even under stealth). Seed the 14 live /rv-model/ URLs harvested
    # from /rv-model-sitemap.xml (2026-04-17). Each URL is one floorplan with
    # real specs (length, GVWR, dry weight, slides). Stealth bypasses WAF.
    "drv": {
        "model_urls": [
            "/rv-model/jx450-drv-luxury-suites-full-house-toy-hauler/",
            "/rv-model/lx455/",
            "/rv-model/ms-36rssb3/",
            "/rv-model/ms-39dbrs3/",
            "/rv-model/ms-40kssb4/",
            "/rv-model/ms-41fkmb/",
            "/rv-model/ms-41fkrb/",
            "/rv-model/ms-41rkdb/",
            "/rv-model/ms-houston/",
            "/rv-model/ms-manhatn/",
            "/rv-model/ms-nashvil/",
            "/rv-model/ms-nashville/",
            "/rv-model/ms-orlando/",
            "/rv-model/mx450-drv-suites/",
        ],
        "force_stealth": True,
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
    # Newmar: parent /models/<slug>/2026-<slug> pages list per-floorplan cards
    # that lazy-load — even under Playwright/stealth the AI classifier can't
    # find them reliably. Each coach has per-floorplan detail pages at
    # /models/<slug>/2026-<slug>/floor-plans/<code> with full specs (length,
    # GVWR, slide count, bedroom). Seed the 65 live floorplan URLs harvested
    # 2026-04-17 from each 2026 series page via stealth. Update the list when
    # Newmar launches/retires a coach or rolls to a new model year.
    "newmar": {
        "model_urls": [
            "/models/bay-star-sport/2026-bay-star-sport/floor-plans/2813",
            "/models/bay-star-sport/2026-bay-star-sport/floor-plans/3014",
            "/models/bay-star-sport/2026-bay-star-sport/floor-plans/3225",
            "/models/bay-star/2026-bay-star/floor-plans/3114",
            "/models/bay-star/2026-bay-star/floor-plans/3225",
            "/models/bay-star/2026-bay-star/floor-plans/3609",
            "/models/bay-star/2026-bay-star/floor-plans/3626",
            "/models/bay-star/2026-bay-star/floor-plans/3629",
            "/models/bay-star/2026-bay-star/floor-plans/3811",
            "/models/bay-star/2026-bay-star/floor-plans/3826",
            "/models/canyon-star/2026-canyon-star/floor-plans/3947",
            "/models/dutch-star/2026-dutch-star/floor-plans/3836",
            "/models/dutch-star/2026-dutch-star/floor-plans/4071",
            "/models/dutch-star/2026-dutch-star/floor-plans/4081",
            "/models/dutch-star/2026-dutch-star/floor-plans/4311",
            "/models/dutch-star/2026-dutch-star/floor-plans/4325",
            "/models/dutch-star/2026-dutch-star/floor-plans/4340",
            "/models/dutch-star/2026-dutch-star/floor-plans/4369",
            "/models/dutch-star/2026-dutch-star/floor-plans/4370",
            "/models/essex/2026-essex/floor-plans/4521",
            "/models/essex/2026-essex/floor-plans/4551",
            "/models/essex/2026-essex/floor-plans/4569",
            "/models/essex/2026-essex/floor-plans/4595",
            "/models/freedom-aire/2026-freedom-aire/floor-plans/2515",
            "/models/grand-star/2026-grand-star/floor-plans/3444",
            "/models/grand-star/2026-grand-star/floor-plans/3940",
            "/models/grand-star/2026-grand-star/floor-plans/3948",
            "/models/king-aire/2026-king-aire/floor-plans/4521",
            "/models/king-aire/2026-king-aire/floor-plans/4531",
            "/models/king-aire/2026-king-aire/floor-plans/4540",
            "/models/king-aire/2026-king-aire/floor-plans/4596",
            "/models/london-aire/2026-london-aire/floor-plans/4540",
            "/models/london-aire/2026-london-aire/floor-plans/4551",
            "/models/london-aire/2026-london-aire/floor-plans/4569",
            "/models/london-aire/2026-london-aire/floor-plans/4595",
            "/models/mountain-aire/2026-mountain-aire/floor-plans/3823",
            "/models/mountain-aire/2026-mountain-aire/floor-plans/3825",
            "/models/mountain-aire/2026-mountain-aire/floor-plans/4118",
            "/models/mountain-aire/2026-mountain-aire/floor-plans/4551",
            "/models/new-aire/2026-new-aire/floor-plans/3543",
            "/models/new-aire/2026-new-aire/floor-plans/3545",
            "/models/new-aire/2026-new-aire/floor-plans/3547",
            "/models/northern-star/2026-northern-star/floor-plans/3418",
            "/models/northern-star/2026-northern-star/floor-plans/3709",
            "/models/northern-star/2026-northern-star/floor-plans/4011",
            "/models/northern-star/2026-northern-star/floor-plans/4037",
            "/models/summit-aire/2026-summit-aire/floor-plans/4505",
            "/models/summit-aire/2026-summit-aire/floor-plans/4540",
            "/models/super-star/2026-super-star/floor-plans/3731",
            "/models/super-star/2026-super-star/floor-plans/4040",
            "/models/super-star/2026-super-star/floor-plans/4059",
            "/models/super-star/2026-super-star/floor-plans/4061",
            "/models/super-star/2026-super-star/floor-plans/4140",
            "/models/super-star/2026-super-star/floor-plans/4159",
            "/models/super-star/2026-super-star/floor-plans/4161",
            "/models/supreme-aire/2026-supreme-aire/floor-plans/3827",
            "/models/supreme-aire/2026-supreme-aire/floor-plans/4129",
            "/models/supreme-aire/2026-supreme-aire/floor-plans/4341",
            "/models/supreme-aire/2026-supreme-aire/floor-plans/4505",
            "/models/supreme-aire/2026-supreme-aire/floor-plans/4540",
            "/models/ventana/2026-ventana/floor-plans/3512",
            "/models/ventana/2026-ventana/floor-plans/3809",
            "/models/ventana/2026-ventana/floor-plans/4037",
            "/models/ventana/2026-ventana/floor-plans/4340",
            "/models/ventana/2026-ventana/floor-plans/4369",
        ],
        "force_stealth": True,
    },
    # Jayco: individual model pages under /rvs/<type>/2026-<slug>/. Floorplan
    # detail sits ~100KB into the rendered HTML (below the old 60KB cut) so
    # the base extractor truncation bump to 150KB is load-bearing here. Exclude
    # /floorplans/ sub-pages (they get re-extracted as separate models with a
    # code-only name) and the /brochure/ download pages.
    "jayco": {
        "listing_pages": [
            "/rvs/travel-trailers",
            "/rvs/fifth-wheels",
            "/rvs/toy-haulers",
            "/rvs/class-a-motorhomes",
            "/rvs/class-b-motorhomes",
            "/rvs/class-c-motorhomes",
            "/rvs/camping-trailers",
        ],
        "model_path_patterns": ["/rvs/"],
        "exclude_patterns": [
            "/floorplans/", "/brochure", "/options",
            "/features", "/specifications", "/standard-features",
        ],
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
    # Storyteller Overland (Shopify, vans under /pages/<vehicle>)
    "storyteller": {
        "model_urls": [
            "/mode",
            "/pages/2026-beast-mode-og",
            "/pages/2026-beast-mode-xo",
            "/pages/2026-classic-mode-og",
            "/pages/2026-classic-mode-xo",
            "/pages/2026-dark-mode-og",
            "/pages/2026-dark-mode-xo",
            "/pages/2026-mode-vans",
            "/pages/2026-tour-mode",
            "/pages/2027-grand-bohemian",
            "/pages/gxv-epic",
            "/pages/gxv-hilt",
            "/pages/storyteller-gxv",
        ],
    },
    # Host Campers (WP site, /product-details-<model>/ URLs)
    "host": {
        "model_urls": [
            "/product-details-cascade/",
            "/product-details-everest/",
            "/product-details-mammoth/",
            "/product-details-tahoe/",
            "/yukon/",
        ],
    },
    # Travel Lite RV (WP site, all models under /rvs/)
    "travel-lite": {
        "model_urls": [
            "/rvs/rove-lite-travel-trailers/",
            "/rvs/rove-lite-classic-lightweight-travel-trailers/",
            "/rvs/2021-super-lite-truck-campers/",
            "/rvs/2022-extended-stay-truck-campers/",
            "/rvs/24sur-toy-hauler/",
        ],
    },
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
