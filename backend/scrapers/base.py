"""Generic AI-powered RV manufacturer scraper.

Given a manufacturer's website, discovers model pages, fetches them, and
extracts structured model/floorplan data using Gemini 2.0 Flash.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from backend.scrapers.brand_configs import get_config
from backend.scrapers.playwright_fetcher import render_page, PLAYWRIGHT_AVAILABLE

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# When a fetched page's content is smaller than this, assume it's JS-rendered
# and fall back to Playwright. Most real model pages are 30KB+.
JS_DETECTION_THRESHOLD = 15000

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@dataclass
class DiscoveredModel:
    url: str
    model_name: str | None = None
    rv_class: str | None = None


@dataclass
class ExtractedFloorplan:
    floorplan_code: str
    length_ft: float | None = None
    sleeping_capacity: int | None = None
    slideout_count: int | None = None
    bed_types: list[str] = field(default_factory=list)
    bathroom_count: int | None = None
    dry_weight_lbs: int | None = None
    gvwr_lbs: int | None = None
    msrp_usd: int | None = None
    standard_features: list[str] = field(default_factory=list)
    source_url: str | None = None


@dataclass
class ExtractedModel:
    model_name: str
    rv_class: str | None = None
    rv_type: str | None = None
    model_year: int | None = None
    length_ft_min: float | None = None
    length_ft_max: float | None = None
    sleeping_capacity_min: int | None = None
    sleeping_capacity_max: int | None = None
    slideout_count_min: int | None = None
    slideout_count_max: int | None = None
    base_msrp_usd: int | None = None
    source_url: str = ""
    floorplans: list[ExtractedFloorplan] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)


class GenericScraper:
    """Fetches an OEM site, discovers model pages, extracts structured data."""

    def __init__(self, manufacturer_slug: str, base_url: str):
        self.slug = manufacturer_slug
        self.base_url = base_url.rstrip("/")
        parsed = urlparse(base_url)
        # Normalize domain by stripping www. — many OEM sites serve at both
        self.domain = parsed.netloc.removeprefix("www.")
        # If base_url has a path (e.g. forestriverinc.com/rvs/travel-trailers/rockwood),
        # the root for sitemap lookups is the domain, but the entry page is the path.
        self.site_root = f"{parsed.scheme}://{parsed.netloc}"
        self.entry_path = parsed.path.rstrip("/") or "/"
        self.config = get_config(manufacturer_slug)

    async def run(self, max_models: int = 30) -> dict:
        """Main entry point. Returns stats dict."""
        start = time.time()
        stats = {
            "slug": self.slug,
            "models_found": 0,
            "models_extracted": 0,
            "floorplans_added": 0,
            "images_found": 0,
            "errors": [],
        }

        try:
            async with httpx.AsyncClient(
                headers=HTTP_HEADERS, timeout=30.0, follow_redirects=True
            ) as client:
                # 1. Discover model URLs
                model_urls = await self._discover_models(client, max_models)
                stats["models_found"] = len(model_urls)

                if not model_urls:
                    stats["errors"].append("No model pages discovered")
                    return stats

                # 2. Extract each model (limit concurrency)
                sem = asyncio.Semaphore(3)
                async def extract_one(url):
                    async with sem:
                        return await self._extract_model(client, url)

                results = await asyncio.gather(
                    *[extract_one(url) for url in model_urls],
                    return_exceptions=True,
                )

                extracted = []
                for r in results:
                    if isinstance(r, Exception):
                        stats["errors"].append(str(r)[:200])
                    elif r is not None:
                        extracted.append(r)

                stats["models_extracted"] = len(extracted)
                stats["floorplans_added"] = sum(len(m.floorplans) for m in extracted)
                stats["images_found"] = sum(len(m.image_urls) for m in extracted)

                # 3. Store in database
                self._persist(extracted)

        except Exception as e:
            stats["errors"].append(f"Fatal: {e}")

        stats["duration_s"] = round(time.time() - start, 1)
        return stats

    async def _discover_models(self, client: httpx.AsyncClient, limit: int) -> list[str]:
        """Find model page URLs via entry_path -> brand config -> sitemap -> generic."""
        urls: set[str] = set()
        has_brand_config = bool(self.config.get("listing_pages"))
        force_playwright = self.config.get("force_playwright", False)

        listing_pages = self.config.get("listing_pages") or [
            "/", "/models", "/rvs", "/products", "/inventory",
            "/our-rvs", "/all-rvs", "/lineup", "/rv-models",
        ]

        # Strategy 0: The base_url itself (crucial for brand-subpath URLs like
        # forestriverinc.com/rvs/travel-trailers/rockwood)
        if self.entry_path not in ("/", ""):
            html = await self._fetch_rendered(client, self.base_url, force_playwright)
            if html and len(html) > JS_DETECTION_THRESHOLD:
                page_urls = await self._ai_find_model_links(self.base_url, html[:80000])
                urls.update(page_urls)

        # Strategy 1: Brand-configured listing pages
        if not urls and has_brand_config:
            for path in listing_pages:
                full = urljoin(self.site_root, path)
                html = await self._fetch_rendered(client, full, force_playwright)
                if html and len(html) > JS_DETECTION_THRESHOLD:
                    page_urls = await self._ai_find_model_links(full, html[:80000])
                    urls.update(page_urls)
                    if len(urls) >= limit:
                        break

        # Strategy 2: sitemap.xml (on site_root, not base_url)
        if not urls:
            for sm_path in [
                "/sitemap.xml", "/sitemap_index.xml", "/sitemap-models.xml",
                "/sitemaps.xml", "/sitemap1.xml",
            ]:
                try:
                    resp = await client.get(urljoin(self.site_root, sm_path))
                    ct = resp.headers.get("content-type", "")
                    if resp.status_code == 200 and ("xml" in ct or resp.text.strip().startswith("<?xml")):
                        sub_sitemaps = re.findall(r"<sitemap>\s*<loc>([^<]+)</loc>", resp.text)
                        if sub_sitemaps:
                            for sub in sub_sitemaps[:5]:
                                try:
                                    r2 = await client.get(sub)
                                    if r2.status_code == 200:
                                        urls.update(self._parse_sitemap_for_models(r2.text))
                                except Exception:
                                    pass
                        urls.update(self._parse_sitemap_for_models(resp.text))
                        if urls:
                            break
                except Exception:
                    pass

        # Strategy 3: generic listing pages with AI
        if not urls:
            for path in listing_pages:
                full = urljoin(self.site_root, path)
                html = await self._fetch_rendered(client, full, force_playwright)
                if html and len(html) > JS_DETECTION_THRESHOLD:
                    page_urls = await self._ai_find_model_links(full, html[:80000])
                    urls.update(page_urls)
                    if len(urls) >= limit:
                        break

        # For sub-brand pages (e.g. rockwood on forestriverinc.com), scope URLs
        # to those that contain the brand's entry path component
        if has_brand_config is False and self.entry_path not in ("/", ""):
            # entry_path's last segment is usually the brand slug
            brand_slug = self.entry_path.rstrip("/").rsplit("/", 1)[-1]
            if brand_slug:
                urls = {u for u in urls if brand_slug.lower() in u.lower()}

        # Normalize and filter to same domain
        filtered = []
        exclude_extras = self.config.get("exclude_patterns", [])
        exclude_kws = [
            "/blog", "/news", "/press", "/dealer", "/warranty",
            "/parts", "/service", "/careers", "/about", "/contact",
            "/privacy", "/terms", "/login", "/sitemap", "/search",
            "/support", "/faq", "/video", "/gallery", "/event",
            ".pdf", ".jpg", ".png", ".webp",
        ] + exclude_extras
        for u in urls:
            parsed = urlparse(u)
            url_domain = parsed.netloc.removeprefix("www.")
            if url_domain and url_domain != self.domain:
                # Allow certain sub-brand domains (e.g. cherokee-rv on forest-river)
                if self.config.get("allow_external_domains", False):
                    pass
                else:
                    continue
            if not parsed.netloc:
                u = urljoin(self.site_root, u)
            path_lower = parsed.path.lower()
            if any(x in path_lower for x in exclude_kws):
                continue
            # Also skip root page and paths with 0-1 segments that look like sections
            if parsed.path in ("", "/"):
                continue
            filtered.append(u)

        # Deduplicate and limit
        return list(dict.fromkeys(filtered))[:limit]

    async def _fetch_rendered(
        self, client: httpx.AsyncClient, url: str, force_playwright: bool = False
    ) -> str:
        """Fetch a page; use Playwright if forced or if httpx returns thin content."""
        if force_playwright and PLAYWRIGHT_AVAILABLE:
            return await render_page(url, timeout_ms=15000)

        try:
            resp = await client.get(url, timeout=20.0)
            if resp.status_code != 200:
                return ""
            html = resp.text
        except Exception:
            return ""

        # If the HTML has very little meaningful text, render with Playwright
        if PLAYWRIGHT_AVAILABLE:
            text_len = len(re.sub(r"<[^>]+>|\s+", " ", html).strip())
            if text_len < 3000:
                rendered = await render_page(url, timeout_ms=15000)
                if rendered and len(rendered) > len(html):
                    return rendered
        return html

    def _parse_sitemap_for_models(self, xml: str) -> list[str]:
        """Extract URLs from sitemap that look like model pages."""
        urls = re.findall(r"<loc>([^<]+)</loc>", xml)
        candidates = []
        # Broad keywords that indicate model/product pages across manufacturer sites
        model_kws = [
            "/model", "/rv/", "/floorplan", "/product",
            "/travel-trailer", "/fifth-wheel", "/fifthwheel", "/toy-hauler",
            "/class-a", "/class-b", "/class-c", "/motorhome", "/coach",
            "/camper", "/trailer", "/towable", "/diesel", "/gas",
        ]
        exclude_kws = [
            "/blog", "/news", "/press", "/dealer", "/warranty", "/parts",
            "/service", "/careers", "/about", "/contact", "/privacy",
            "/terms", "/login", "/support", "/faq", "/video", "/gallery",
            "/recall", "/safety", ".pdf", ".jpg", ".png", ".webp",
            "/event", "/rally", "/shopping-tools", "/landing-pages",
            "/company", "/find-a", "/shop-",
        ]
        for url in urls:
            path = urlparse(url).path.lower()
            if any(x in path for x in exclude_kws):
                continue
            if any(kw in path for kw in model_kws):
                candidates.append(url)
        return candidates

    async def _ai_find_model_links(self, page_url: str, html: str) -> list[str]:
        """Use Gemini to identify model page links from a listing page."""
        # Extract anchor opening tags with their inner content (supports nested HTML)
        anchor_iter = re.finditer(
            r'<a\b[^>]*\bhref=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            html, flags=re.DOTALL | re.IGNORECASE,
        )

        # Build a list of (href, text) pairs, dedupe
        links_text = []
        seen = set()
        for match in anchor_iter:
            href = match.group(1).strip()
            # Strip HTML tags from inner content to get just the text
            inner = re.sub(r"<[^>]+>", " ", match.group(2))
            text = re.sub(r"\s+", " ", inner).strip()[:120]
            if href in seen or not href:
                continue
            seen.add(href)
            # Keep even textless anchors (image-only links common on model cards)
            links_text.append(f"{href} | {text or '(no text)'}")
            if len(links_text) >= 250:
                break

        if not links_text:
            return []

        links_str = "\n".join(links_text[:150])
        prompt = (
            "You are filtering links from an RV manufacturer's website. "
            "From this list of hyperlinks (format: URL | link text), return ONLY the URLs "
            "that link to a specific RV model/product page (e.g., individual travel trailer, "
            "motorhome, or fifth wheel models). EXCLUDE dealer locators, about pages, "
            "blog posts, news, warranty, parts, service, careers.\n\n"
            f"Links:\n{links_str}\n\n"
            "Respond with ONLY a JSON array of URLs, no explanation. Example: "
            '["url1","url2"]. If none found, return []'
        )

        response = await self._call_gemini(prompt)
        try:
            # Extract JSON array from response
            match = re.search(r"\[.*?\]", response, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception:
            pass
        return []

    async def _extract_model(
        self, client: httpx.AsyncClient, url: str
    ) -> ExtractedModel | None:
        """Fetch a model page and extract structured data via Gemini.

        Tries httpx first; if content is thin (JS-rendered), falls back to
        Playwright. Retries transient failures once.
        """
        html = ""
        for attempt in range(2):
            try:
                resp = await client.get(url, timeout=20.0)
                if resp.status_code == 200:
                    html = resp.text
                    break
                elif resp.status_code in (429, 502, 503):
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    return None
            except (httpx.TimeoutException, httpx.ConnectError):
                if attempt == 0:
                    await asyncio.sleep(1)
                    continue
                return None
            except Exception:
                return None

        # If content is thin (JS-heavy SPA), render with Playwright
        meaningful_text_len = len(re.sub(r"<[^>]+>|\s+", " ", html).strip())
        if meaningful_text_len < 3000 and PLAYWRIGHT_AVAILABLE:
            rendered = await render_page(url, timeout_ms=15000)
            if rendered and len(rendered) > len(html):
                html = rendered

        if not html:
            return None

        # Strip script/style content but keep structure
        html_clean = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        html_clean = re.sub(r"<style[^>]*>.*?</style>", "", html_clean, flags=re.DOTALL)
        # Collapse whitespace
        html_clean = re.sub(r"\s+", " ", html_clean)
        # Limit size
        html_clean = html_clean[:60000]

        # Find images in the HTML
        image_urls = self._extract_image_urls(html, url)

        prompt = f"""Extract RV model information from this manufacturer page.

Source URL: {url}

Return a JSON object with these fields (use null for unknown):
- model_name (string, required)
- rv_class (one of: "Class A", "Class B", "Class B+", "Class C", "Fifth Wheel", "Travel Trailer", "Toy Hauler", "Truck Camper", "Pop-Up", "Park Model")
- rv_type ("motorized" or "towable")
- model_year (int, e.g. 2026)
- length_ft_min, length_ft_max (float, feet)
- sleeping_capacity_min, sleeping_capacity_max (int)
- slideout_count_min, slideout_count_max (int)
- base_msrp_usd (int, USD)
- floorplans: array of objects with fields:
  - floorplan_code (e.g. "28BH", "Model T23RB")
  - length_ft (float)
  - sleeping_capacity (int)
  - slideout_count (int)
  - bathroom_count (int)
  - dry_weight_lbs (int)
  - gvwr_lbs (int)
  - msrp_usd (int)

If the page is NOT a single model page (e.g. it's a category listing), return null.

HTML content:
{html_clean}

Respond with ONLY the JSON, no markdown formatting."""

        response = await self._call_gemini(prompt)
        data = self._parse_json(response)
        if not data or not isinstance(data, dict) or not data.get("model_name"):
            return None

        model = ExtractedModel(
            model_name=data["model_name"],
            rv_class=data.get("rv_class"),
            rv_type=data.get("rv_type"),
            model_year=data.get("model_year"),
            length_ft_min=data.get("length_ft_min"),
            length_ft_max=data.get("length_ft_max"),
            sleeping_capacity_min=data.get("sleeping_capacity_min"),
            sleeping_capacity_max=data.get("sleeping_capacity_max"),
            slideout_count_min=data.get("slideout_count_min"),
            slideout_count_max=data.get("slideout_count_max"),
            base_msrp_usd=data.get("base_msrp_usd"),
            source_url=url,
            image_urls=image_urls[:20],
        )

        for fp in data.get("floorplans") or []:
            if not isinstance(fp, dict) or not fp.get("floorplan_code"):
                continue
            model.floorplans.append(
                ExtractedFloorplan(
                    floorplan_code=str(fp["floorplan_code"]),
                    length_ft=fp.get("length_ft"),
                    sleeping_capacity=fp.get("sleeping_capacity"),
                    slideout_count=fp.get("slideout_count"),
                    bathroom_count=fp.get("bathroom_count"),
                    dry_weight_lbs=fp.get("dry_weight_lbs"),
                    gvwr_lbs=fp.get("gvwr_lbs"),
                    msrp_usd=fp.get("msrp_usd"),
                    source_url=url,
                )
            )

        return model

    def _extract_image_urls(self, html: str, page_url: str) -> list[str]:
        """Find candidate image URLs on the page."""
        imgs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html)
        results = []
        for src in imgs:
            if src.startswith("data:") or len(src) < 10:
                continue
            full = urljoin(page_url, src)
            if any(ext in full.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                results.append(full)
        return list(dict.fromkeys(results))

    async def _call_gemini(self, prompt: str, max_retries: int = 2) -> str:
        """Call Gemini API with retry on rate limit."""
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY not set")

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 4096,
                "responseMimeType": "application/json",
            },
        }

        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 429:
                        await asyncio.sleep(5 * (attempt + 1))
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:
                if attempt == max_retries:
                    raise
                await asyncio.sleep(2)
        return ""

    def _parse_json(self, text: str) -> Any:
        """Extract JSON from Gemini response (may have markdown fences)."""
        text = text.strip()
        # Strip markdown fences
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except Exception:
            return None

    def _persist(self, models: list[ExtractedModel]):
        """Save extracted models to the database."""
        from backend.database import get_db

        db = get_db()
        # Get manufacturer id
        mfr = db.execute(
            "SELECT id FROM manufacturers WHERE slug = ?", (self.slug,)
        ).fetchone()
        if not mfr:
            db.close()
            return
        mfr_id = mfr["id"]

        for m in models:
            # Insert or ignore model
            db.execute(
                """INSERT OR IGNORE INTO models
                   (manufacturer_id, manufacturer_slug, model_year, model_name,
                    rv_class, rv_type, length_ft_min, length_ft_max,
                    sleeping_capacity_min, sleeping_capacity_max,
                    slideout_count_min, slideout_count_max, base_msrp_usd,
                    source_url, data_quality)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'scraped')""",
                (
                    mfr_id, self.slug, m.model_year, m.model_name,
                    m.rv_class, m.rv_type, m.length_ft_min, m.length_ft_max,
                    m.sleeping_capacity_min, m.sleeping_capacity_max,
                    m.slideout_count_min, m.slideout_count_max, m.base_msrp_usd,
                    m.source_url,
                ),
            )

            # Get model id
            model_row = db.execute(
                "SELECT id FROM models WHERE manufacturer_slug = ? AND model_name = ? AND (model_year = ? OR (model_year IS NULL AND ? IS NULL))",
                (self.slug, m.model_name, m.model_year, m.model_year),
            ).fetchone()
            if not model_row:
                continue
            model_id = model_row["id"]

            # Insert floorplans
            for fp in m.floorplans:
                try:
                    db.execute(
                        """INSERT OR IGNORE INTO floorplans
                           (model_id, manufacturer_slug, model_name, model_year,
                            floorplan_code, length_ft, sleeping_capacity,
                            slideout_count, bathroom_count, dry_weight_lbs,
                            gvwr_lbs, msrp_usd, bed_types, standard_features,
                            source_url, data_quality)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'scraped')""",
                        (
                            model_id, self.slug, m.model_name, m.model_year,
                            fp.floorplan_code, fp.length_ft, fp.sleeping_capacity,
                            fp.slideout_count, fp.bathroom_count, fp.dry_weight_lbs,
                            fp.gvwr_lbs, fp.msrp_usd,
                            json.dumps(fp.bed_types), json.dumps(fp.standard_features),
                            fp.source_url,
                        ),
                    )
                except Exception:
                    pass

            # Insert images
            for img_url in m.image_urls:
                try:
                    db.execute(
                        """INSERT OR IGNORE INTO images
                           (model_id, manufacturer_slug, model_name, image_type, source_url)
                           VALUES (?,?,?, 'exterior', ?)""",
                        (model_id, self.slug, m.model_name, img_url),
                    )
                except Exception:
                    pass

        # Update denormalized counts
        counts = db.execute(
            """SELECT
                (SELECT COUNT(*) FROM models WHERE manufacturer_slug = ?) as mc,
                (SELECT COUNT(*) FROM floorplans WHERE manufacturer_slug = ?) as fc,
                (SELECT COUNT(*) FROM images WHERE manufacturer_slug = ?) as ic""",
            (self.slug, self.slug, self.slug),
        ).fetchone()

        db.execute(
            """UPDATE manufacturers SET
               model_count = ?, floorplan_count = ?, image_count = ?,
               scrape_status = CASE
                 WHEN ? > 0 THEN 'partial'
                 ELSE scrape_status
               END,
               last_scraped_at = datetime('now', 'utc')
               WHERE slug = ?""",
            (counts["mc"], counts["fc"], counts["ic"], counts["mc"], self.slug),
        )
        db.commit()
        db.close()
