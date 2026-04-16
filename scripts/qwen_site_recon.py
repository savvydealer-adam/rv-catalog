"""Use local Qwen3 32B (via Ollama) to recon OEM sites and propose brand_configs entries.

For each manufacturer with zero models, render the homepage with Playwright,
extract the anchor list, and ask Qwen to identify model-listing pages.
Output: scripts/qwen_site_recon.json for human review before merging into
backend/scrapers/brand_configs.py.

Usage:
  python scripts/qwen_site_recon.py                  # all 0-model brands
  python scripts/qwen_site_recon.py --slug jayco     # one brand
  python scripts/qwen_site_recon.py --limit 5        # first N (for smoke test)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import get_db
from backend.scrapers.playwright_fetcher import render_page, cleanup as pw_cleanup

OLLAMA_URL = "http://127.0.0.1:11434/v1/chat/completions"
OLLAMA_MODEL = "qwen3:32b"
OUTPUT_PATH = Path(__file__).resolve().parent / "qwen_site_recon.json"

# Ollama serves one 32B request at a time; any parallelism just queues and
# burns our per-call timeout. Serialize Qwen calls while leaving fetch/render
# parallel (those are network-bound and benefit from concurrency).
_qwen_lock = asyncio.Lock()

_IPROYAL_HOST = os.getenv("CD_IPROYAL_HOST", "geo.iproyal.com:12321")


def iproyal_httpx_proxy(session: str, retry: int = 0) -> str | None:
    """Build an IPRoyal proxy URL for httpx. Rotating-residential plan:
    per-request IP change, no session stickiness (suffix params trigger 407).
    """
    user = os.getenv("CD_IPROYAL_USER", "").strip()
    pwd = os.getenv("CD_IPROYAL_PASS", "").strip()
    if not user or not pwd:
        return None
    _ = session, retry
    return f"http://{user}:{pwd}@{_IPROYAL_HOST}"


def extract_anchors(html: str, base_url: str, limit: int = 200) -> list[dict]:
    """Pull (href, text) pairs from anchor tags, same-domain only."""
    base_domain = urlparse(base_url).netloc.removeprefix("www.")
    anchors = []
    seen = set()
    for m in re.finditer(
        r'<a\b[^>]*\bhref=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        html, flags=re.DOTALL | re.IGNORECASE,
    ):
        href = m.group(1).strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        domain = parsed.netloc.removeprefix("www.")
        if domain and domain != base_domain:
            continue
        path = parsed.path.rstrip("/") or "/"
        if path in seen:
            continue
        seen.add(path)
        text = re.sub(r"<[^>]+>", " ", m.group(2))
        text = re.sub(r"\s+", " ", text).strip()[:80]
        anchors.append({"path": path, "text": text or "(no text)"})
        if len(anchors) >= limit:
            break
    return anchors


async def ask_qwen(anchors: list[dict], brand: str, website: str) -> dict:
    """Ask Qwen3 32B to identify model-listing pages from the anchor set."""
    anchor_text = "\n".join(f"{a['path']} | {a['text']}" for a in anchors[:150])
    prompt = f"""You are analyzing the homepage of an RV manufacturer website to find category/listing pages that contain links to individual RV models.

Manufacturer: {brand}
Website: {website}

You are given a list of links from the homepage (format: URL path | link text).
Identify paths that likely lead to pages listing multiple RV models by category.

GOOD examples (category/listing pages):
  /travel-trailers, /fifth-wheels, /toy-haulers, /motorhomes
  /class-a, /class-b, /class-c, /class-b-plus
  /rvs, /models, /our-rvs, /lineup, /products

EXCLUDE:
  /dealer-locator, /about, /contact, /blog, /news, /warranty, /parts,
  /service, /careers, /privacy, /terms, /login, /faq, /gallery, /video,
  pages that link to a single specific model (those come from listing pages).

Return ONLY valid JSON with this schema:
{{
  "listing_pages": ["/travel-trailers", "/fifth-wheels"],
  "notes": "brief observation about site structure (one sentence)"
}}

Links:
{anchor_text}
"""
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": "You return only valid JSON. No prose."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
    }
    async with _qwen_lock:
        async with httpx.AsyncClient(timeout=600.0) as client:
            resp = await client.post(OLLAMA_URL, json=payload)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return {"listing_pages": [], "notes": "Qwen returned no JSON"}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        return {"listing_pages": [], "notes": f"JSON parse error: {e}"}


def detect_js_heavy(raw_html: str, rendered_html: str) -> bool:
    """A site is JS-heavy if rendered content is substantially larger than raw."""
    raw_text = len(re.sub(r"<[^>]+>|\s+", " ", raw_html).strip())
    rendered_text = len(re.sub(r"<[^>]+>|\s+", " ", rendered_html).strip())
    if rendered_text > raw_text * 2 and rendered_text > 3000:
        return True
    if raw_text < 2000 and rendered_text > 3000:
        return True
    return False


async def recon_brand(slug: str, name: str, website: str) -> dict:
    """Run recon on one manufacturer. Returns the result record."""
    start = time.time()
    result = {
        "slug": slug,
        "name": name,
        "website": website,
        "listing_pages": [],
        "force_playwright": False,
        "notes": "",
        "anchor_count": 0,
        "duration_s": 0,
        "error": None,
    }

    try:
        # Fetch raw (httpx) and rendered (Playwright) — both routed through
        # the same sticky IPRoyal session so the site sees one residential IP.
        proxy_url = iproyal_httpx_proxy(slug)
        client_kwargs = dict(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=45.0, follow_redirects=True, trust_env=False,
        )
        if proxy_url:
            client_kwargs["proxy"] = proxy_url
        async with httpx.AsyncClient(**client_kwargs) as client:
            try:
                raw = (await client.get(website)).text
            except Exception:
                raw = ""
        rendered = await render_page(website, timeout_ms=35000, session=slug)
        html = rendered if len(rendered) > len(raw) else raw
        if not html:
            result["error"] = "No HTML retrieved (raw or rendered)"
            return result

        result["force_playwright"] = detect_js_heavy(raw, rendered)

        anchors = extract_anchors(html, website)
        result["anchor_count"] = len(anchors)
        if not anchors:
            result["error"] = "No anchors extracted"
            return result

        qwen_out = await ask_qwen(anchors, name, website)
        result["listing_pages"] = qwen_out.get("listing_pages", []) or []
        result["notes"] = qwen_out.get("notes", "") or ""

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    finally:
        result["duration_s"] = round(time.time() - start, 1)

    return result


def load_targets(
    slug: str | None, limit: int | None, retry_errors: bool = False
) -> list[dict]:
    if retry_errors and OUTPUT_PATH.exists():
        existing = json.loads(OUTPUT_PATH.read_text())
        failed_slugs = {
            r["slug"] for r in existing.get("results", [])
            if r.get("error") or (not r.get("error") and not r.get("listing_pages"))
        }
        if not failed_slugs:
            return []
        db = get_db()
        placeholders = ",".join("?" * len(failed_slugs))
        rows = db.execute(
            f"SELECT slug, name, website FROM manufacturers WHERE slug IN ({placeholders})",
            tuple(failed_slugs),
        ).fetchall()
        db.close()
        return [dict(r) for r in rows]

    db = get_db()
    q = """
      SELECT m.slug, m.name, m.website
      FROM manufacturers m
      LEFT JOIN models md ON md.manufacturer_id = m.id
      WHERE m.website IS NOT NULL AND m.website != ''
    """
    if slug:
        q += " AND m.slug = ?"
        rows = db.execute(q + " GROUP BY m.id", (slug,)).fetchall()
    else:
        q += " GROUP BY m.id HAVING COUNT(md.id) = 0 ORDER BY m.tier, m.scrape_priority"
        rows = db.execute(q).fetchall()
    db.close()
    targets = [dict(r) for r in rows]
    if limit:
        targets = targets[:limit]
    return targets


def merge_results(new_results: list[dict]) -> list[dict]:
    """Merge new results into existing JSON, preferring newer non-error entries."""
    if not OUTPUT_PATH.exists():
        return new_results
    existing = json.loads(OUTPUT_PATH.read_text()).get("results", [])
    by_slug = {r["slug"]: r for r in existing}
    for r in new_results:
        prior = by_slug.get(r["slug"])
        # Replace if we now have a success, or if prior didn't exist
        if prior is None or (not r.get("error") and r.get("listing_pages")):
            by_slug[r["slug"]] = r
        elif prior.get("error") and not r.get("error"):
            # Prior was error, now we have at least a clean run (even if empty)
            by_slug[r["slug"]] = r
    return list(by_slug.values())


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", help="Single brand slug")
    ap.add_argument("--limit", type=int, help="Max brands (for smoke tests)")
    ap.add_argument("--retry-errors", action="store_true",
                    help="Retry only brands that errored or got no listing_pages previously")
    ap.add_argument("--concurrency", type=int, default=3,
                    help="Parallel browser renders (Qwen calls serialize on Ollama)")
    args = ap.parse_args()

    targets = load_targets(args.slug, args.limit, retry_errors=args.retry_errors)
    if not targets:
        print("No targets")
        return

    proxy_on = bool(os.getenv("CD_IPROYAL_USER") and os.getenv("CD_IPROYAL_PASS"))
    print(f"Reconning {len(targets)} manufacturers with Qwen3:32b "
          f"(concurrency={args.concurrency}, iproyal={'on' if proxy_on else 'off'})")
    print(f"Output: {OUTPUT_PATH}")

    sem = asyncio.Semaphore(args.concurrency)
    results: list[dict] = []

    async def bounded(t):
        async with sem:
            print(f"  -> {t['slug']:30s} {t['website']}")
            r = await recon_brand(t["slug"], t["name"], t["website"])
            status = "ERR" if r["error"] else f"{len(r['listing_pages'])} paths"
            pw = " [pw]" if r["force_playwright"] else ""
            print(f"  <- {t['slug']:30s} {status}{pw} ({r['duration_s']}s)"
                  + (f" — {r['error']}" if r["error"] else ""))
            results.append(r)
            # Write incrementally so Ctrl-C doesn't lose everything
            merged = merge_results(results)
            OUTPUT_PATH.write_text(
                json.dumps({"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "results": merged}, indent=2)
            )
            return r

    await asyncio.gather(*[bounded(t) for t in targets])
    await pw_cleanup()

    hits = sum(1 for r in results if r["listing_pages"] and not r["error"])
    print(f"\nDone. {hits}/{len(results)} brands produced listing_pages proposals")
    print(f"Review: {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
