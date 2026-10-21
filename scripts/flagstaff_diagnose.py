"""Read-only diagnostic: replay flagstaff-rv discovery, then fetch each discovered
model URL with the scraper's own client/proxy logic. Prints status + content
lengths + <title>. No DB writes, no image downloads, no Gemini extraction."""

import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import httpx

from backend.scrapers.base import GenericScraper, HTTP_HEADERS, proxy_url_for, PLAYWRIGHT_AVAILABLE

SLUG = "flagstaff-rv"
BASE = "https://forestriverinc.com/rvs/travel-trailers/flagstaff"


async def main() -> None:
    sc = GenericScraper(SLUG, BASE)
    proxy = proxy_url_for(SLUG)
    print(f"proxy for {SLUG}: {proxy}")
    print(f"PLAYWRIGHT_AVAILABLE: {PLAYWRIGHT_AVAILABLE}")

    kwargs = dict(headers=HTTP_HEADERS, timeout=30.0, follow_redirects=True)
    if proxy:
        kwargs["proxy"] = proxy
        kwargs["trust_env"] = False

    async with httpx.AsyncClient(**kwargs) as client:
        # Entry page
        try:
            r = await client.get(BASE)
            print(f"ENTRY {BASE} -> {r.status_code} len={len(r.text)}")
        except Exception as e:
            print(f"ENTRY {BASE} -> EXC {type(e).__name__}: {e}")

        model_urls = await sc._discover_models(client, 30)
        print(f"\nDISCOVERED {len(model_urls)} model URLs:")
        for u in model_urls:
            try:
                r = await client.get(u, timeout=20.0)
                title = ""
                m = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.I | re.S)
                if m:
                    title = re.sub(r"\s+", " ", m.group(1)).strip()[:100]
                meaning = len(re.sub(r"<[^>]+>|\s+", " ", r.text).strip())
                print(f"  {r.status_code} len={len(r.text):>7} text={meaning:>6} {u}")
                print(f"        title: {title}")
            except Exception as e:
                print(f"  EXC {type(e).__name__}: {str(e)[:120]} {u}")
        await client.aclose()


asyncio.run(main())
