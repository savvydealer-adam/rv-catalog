"""One-shot harvester: walks each Newmar model series page and extracts
the per-floorplan URLs. Writes them to data/tmp_newmar_floorplans.json.

Run once, copy the results into brand_configs.py.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.scrapers.stealth_fetcher import stealth_fetch

SERIES_URLS = [
    "https://www.newmarcorp.com/models/bay-star-sport/2026-bay-star-sport",
    "https://www.newmarcorp.com/models/bay-star/2026-bay-star",
    "https://www.newmarcorp.com/models/canyon-star/2026-canyon-star",
    "https://www.newmarcorp.com/models/dutch-star/2026-dutch-star",
    "https://www.newmarcorp.com/models/essex/2026-essex",
    "https://www.newmarcorp.com/models/freedom-aire/2026-freedom-aire",
    "https://www.newmarcorp.com/models/grand-star/2026-grand-star",
    "https://www.newmarcorp.com/models/king-aire/2026-king-aire",
    "https://www.newmarcorp.com/models/london-aire/2026-london-aire",
    "https://www.newmarcorp.com/models/mountain-aire/2026-mountain-aire",
    "https://www.newmarcorp.com/models/new-aire/2026-new-aire",
    "https://www.newmarcorp.com/models/northern-star/2026-northern-star",
    "https://www.newmarcorp.com/models/summit-aire/2026-summit-aire",
    "https://www.newmarcorp.com/models/super-star/2026-super-star",
    "https://www.newmarcorp.com/models/supreme-aire/2026-supreme-aire",
    "https://www.newmarcorp.com/models/ventana/2026-ventana",
]


async def harvest_one(series_url: str) -> list[str]:
    html = await stealth_fetch(
        series_url, networkidle=True, settle_ms=3000, timeout_ms=45000
    )
    if not html:
        return []
    hrefs = re.findall(r'href=["\'](/?[^"\'#]*?/floor-plans/\d+)["\']', html)
    # Dedupe, keep order
    return list(dict.fromkeys(hrefs))


async def main():
    out: dict[str, list[str]] = {}
    for url in SERIES_URLS:
        print(f"Harvesting {url}")
        fps = await harvest_one(url)
        print(f"  -> {len(fps)} floorplans")
        out[url] = fps
    # Flatten to a deduped list of paths
    all_paths: list[str] = []
    for fps in out.values():
        all_paths.extend(fps)
    all_paths = list(dict.fromkeys(all_paths))
    result = {
        "series": out,
        "all_paths": all_paths,
        "count": len(all_paths),
    }
    Path("data/tmp_newmar_floorplans.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(f"\nTotal floorplan URLs: {len(all_paths)}")


if __name__ == "__main__":
    asyncio.run(main())
