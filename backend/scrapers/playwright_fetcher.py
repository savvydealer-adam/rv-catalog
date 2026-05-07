"""Playwright-based page fetcher for JS-heavy sites.

Playwright runs proxyless. Chromium's proxy-auth path is fragile against
residential gateways (the IPRoyal era surfaced ERR_PROXY_AUTH_UNSUPPORTED /
ERR_TUNNEL_CONNECTION_FAILED, and the same class of bug is untested against
the home-proxy pool). The httpx path in `base.py` routes through the
Tailscale home-proxy pool — that's where rotation happens. Playwright
inherits whatever residential IP the host machine has (main PC = Comcast,
Dell = Spectrum), which is fine for the JS-render fallback path.

Env vars (all optional — absent = direct connection):
  PROXY_POOL                          Newline/comma-separated proxy URLs
                                      (single explicit override, no auth).
                                      http://host:port
"""

from __future__ import annotations

import asyncio
import itertools
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from urllib.parse import urlparse

try:
    from playwright.async_api import async_playwright, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


_browser_lock = asyncio.Lock()
_browser: "Browser | None" = None
_proxy_cycle: itertools.cycle | None = None
_proxy_cycle_lock = asyncio.Lock()


def _parse_proxy_url(url: str) -> dict | None:
    """Turn a proxy URL into Playwright's proxy dict shape (no auth)."""
    url = url.strip()
    if not url:
        return None
    parsed = urlparse(url)
    if not parsed.hostname:
        return None
    server = f"{parsed.scheme or 'http'}://{parsed.hostname}"
    if parsed.port:
        server += f":{parsed.port}"
    return {"server": server}


def _load_proxy_pool() -> list[dict]:
    """Optional manual override pool from PROXY_POOL env (no auth)."""
    pool: list[dict] = []
    raw_pool = os.getenv("PROXY_POOL", "").strip()
    if raw_pool:
        for token in raw_pool.replace("\n", ",").split(","):
            p = _parse_proxy_url(token)
            if p:
                pool.append(p)
    return pool


async def _next_pool_proxy() -> dict | None:
    """Pick the next proxy from the manual override pool (round-robin)."""
    global _proxy_cycle
    async with _proxy_cycle_lock:
        if _proxy_cycle is None:
            pool = _load_proxy_pool()
            if not pool:
                _proxy_cycle = itertools.cycle([None])
                return None
            _proxy_cycle = itertools.cycle(pool)
        proxy = next(_proxy_cycle)
    return dict(proxy) if proxy else None


@asynccontextmanager
async def _shared_browser() -> AsyncGenerator["Browser", None]:
    """Share a single Playwright browser across scrape runs."""
    global _browser
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError("Playwright not installed")

    async with _browser_lock:
        if _browser is None:
            p = await async_playwright().start()
            _browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
    yield _browser


async def render_page(
    url: str,
    wait_selector: str | None = None,
    timeout_ms: int = 20000,
    session: str | None = None,  # noqa: ARG001 — kept for caller compat
    retry: int = 0,  # noqa: ARG001
) -> str:
    """Fetch a URL with JS rendering. Returns fully rendered HTML.

    Runs proxyless by default (see module docstring). PROXY_POOL is honored
    only as a manual override — useful for one-off testing of explicit
    upstream proxies that don't need auth.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return ""

    proxy = await _next_pool_proxy()

    html = await _goto_and_content(
        url, wait_selector=wait_selector, timeout_ms=timeout_ms, proxy=proxy
    )
    if not html and proxy:
        # Manual-override proxy refused; retry direct.
        html = await _goto_and_content(
            url, wait_selector=wait_selector, timeout_ms=timeout_ms, proxy=None
        )
    return html


async def _goto_and_content(
    url: str,
    wait_selector: str | None,
    timeout_ms: int,
    proxy: dict | None,
) -> str:
    async with _shared_browser() as browser:
        context_kwargs: dict = {
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            ),
            "viewport": {"width": 1280, "height": 720},
        }
        if proxy:
            context_kwargs["proxy"] = proxy
        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                if wait_selector:
                    await page.wait_for_selector(wait_selector, timeout=8000)
                else:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                    try:
                        await page.wait_for_function(
                            "document.querySelectorAll('a[href]').length > 5",
                            timeout=5000,
                        )
                    except Exception:
                        pass
            except Exception:
                pass
            return await page.content()
        except Exception:
            return ""
        finally:
            await context.close()


async def cleanup():
    """Close the shared browser (call at end of scrape run)."""
    global _browser, _proxy_cycle
    if _browser is not None:
        try:
            await _browser.close()
        except Exception:
            pass
        _browser = None
    _proxy_cycle = None
