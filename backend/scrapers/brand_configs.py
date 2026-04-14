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
        "force_playwright": True,
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
    },
    # Heartland: models under /travel-trailers/, /fifth-wheels/, /toy-haulers/
    "heartland": {
        "listing_pages": [
            "/travel-trailers",
            "/fifth-wheels",
            "/toy-haulers",
            "/destination-trailers",
        ],
        "force_playwright": True,
    },
    # Coachmen: split motorhomes/towables sections
    "coachmen": {
        "listing_pages": [
            "/motorized",
            "/towables",
            "/class-a",
            "/class-b",
            "/class-c",
            "/travel-trailers",
            "/fifth-wheels",
        ],
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
    # Cherokee RV brands
    "cherokee-rv": {
        "listing_pages": [
            "/models",
            "/grey-wolf",
            "/arctic-wolf",
            "/wolf-pup",
            "/alpha-wolf",
            "/black-label",
        ],
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
}


def get_config(slug: str) -> BrandConfig:
    return CONFIGS.get(slug, {})
