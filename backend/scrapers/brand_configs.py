"""Per-brand scraping configuration overrides.

Most OEM sites work with the generic scraper (sitemap.xml -> model pages).
But some use unconventional URL structures that need specific guidance.
"""

from typing import TypedDict


class BrandConfig(TypedDict, total=False):
    # Seed URLs to crawl for model discovery (category/listing pages)
    listing_pages: list[str]
    # URL path patterns that indicate a model page (in addition to defaults)
    model_path_patterns: list[str]
    # URL path patterns to exclude (in addition to defaults)
    exclude_patterns: list[str]
    # Force Playwright rendering for this brand (JS-heavy site)
    force_playwright: bool
    # Force puppeteer-real-browser (WAF bypass, Cloudflare Turnstile, local PC only)
    force_stealth: bool


CONFIGS: dict[str, BrandConfig] = {
    # Thor Motor Coach: models at top level like /ace, /hurricane (SPA-rendered)
    "thor-motor-coach": {
        "listing_pages": [
            "/motorhomes/class-a-motorhomes",
            "/motorhomes/class-c-motorhomes",
            "/motorhomes/class-b-motorhomes",
            "/motorhomes/camper-vans",
            "/motorhomes/diesel-motorhomes",
            "/motorhomes/sprinter-vans",
            "/motorhomes/toy-haulers",
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
    # Coachmen: split motorhomes/towables sections
    "coachmen": {
        "listing_pages": [
            "/brands",
            "/motorized",
            "/towables",
            "/class-a",
            "/class-b",
            "/class-c",
            "/travel-trailers",
            "/fifth-wheels",
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
}


def get_config(slug: str) -> BrandConfig:
    return CONFIGS.get(slug, {})
