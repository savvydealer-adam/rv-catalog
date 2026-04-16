"""Playwright-based page fetcher for JS-heavy sites.

Supports residential proxy routing via IPRoyal (primary) or a generic
proxy pool. Each render can opt into a sticky per-session exit IP so that
parallel scrapes of different brands crawl from distinct residential IPs.

Env vars (all optional — absent = direct connection):
  CD_IPROYAL_USER / CD_IPROYAL_PASS   IPRoyal residential gateway creds
                                      (same secret names as competitive-dashboard).
  CD_IPROYAL_HOST                     Gateway host:port (default geo.iproyal.com:12321)

  PROXY_POOL                          Newline/comma-separated proxy URLs
                                      (fallback when IPRoyal creds not set).
                                      http(s)://[user:pass@]host:port
  PROXY_SERVER / PROXY_USERNAME / PROXY_PASSWORD
                                      Single-endpoint fallback. Username may
                                      include "{session}" which is replaced
                                      with a random hex token per context.
"""

from __future__ import annotations

import asyncio
import itertools
import os
import secrets
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from urllib.parse import urlparse, unquote

try:
    from playwright.async_api import async_playwright, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


_browser_lock = asyncio.Lock()
_browser: "Browser | None" = None
_proxy_cycle: itertools.cycle | None = None
_proxy_cycle_lock = asyncio.Lock()

_IPROYAL_HOST = os.getenv("CD_IPROYAL_HOST", "geo.iproyal.com:12321")


def _iproyal_proxy(session: str | None, retry: int = 0) -> dict | None:
    """Build a Playwright-shaped IPRoyal proxy dict.

    This account is on rotating-residential (per-request IP change); session
    and country suffixes are not supported and produce HTTP 407. We keep the
    session/retry params on the signature for forward compatibility with
    sticky-session plans.
    """
    user = os.getenv("CD_IPROYAL_USER", "").strip()
    pwd = os.getenv("CD_IPROYAL_PASS", "").strip()
    if not user or not pwd:
        return None
    _ = session, retry
    return {
        "server": f"http://{_IPROYAL_HOST}",
        "username": user,
        "password": pwd,
    }


def _parse_proxy_url(url: str) -> dict | None:
    """Turn a proxy URL into Playwright's proxy dict shape."""
    url = url.strip()
    if not url:
        return None
    parsed = urlparse(url)
    if not parsed.hostname:
        return None
    server = f"{parsed.scheme or 'http'}://{parsed.hostname}"
    if parsed.port:
        server += f":{parsed.port}"
    proxy = {"server": server}
    if parsed.username:
        proxy["username"] = unquote(parsed.username)
    if parsed.password:
        proxy["password"] = unquote(parsed.password)
    return proxy


def _load_proxy_pool() -> list[dict]:
    """Build the fallback proxy pool from PROXY_POOL / PROXY_SERVER env vars."""
    pool: list[dict] = []
    raw_pool = os.getenv("PROXY_POOL", "").strip()
    if raw_pool:
        for token in raw_pool.replace("\n", ",").split(","):
            p = _parse_proxy_url(token)
            if p:
                pool.append(p)

    single = os.getenv("PROXY_SERVER", "").strip()
    if single:
        p = _parse_proxy_url(single)
        if p:
            user = os.getenv("PROXY_USERNAME", "").strip()
            pw = os.getenv("PROXY_PASSWORD", "").strip()
            if user:
                p["username"] = user
            if pw:
                p["password"] = pw
            pool.append(p)
    return pool


async def _next_pool_proxy() -> dict | None:
    """Pick the next proxy from the fallback pool (round-robin)."""
    global _proxy_cycle
    async with _proxy_cycle_lock:
        if _proxy_cycle is None:
            pool = _load_proxy_pool()
            if not pool:
                _proxy_cycle = itertools.cycle([None])
                return None
            _proxy_cycle = itertools.cycle(pool)
        proxy = next(_proxy_cycle)
    if not proxy:
        return None
    proxy = dict(proxy)
    if "username" in proxy and "{session}" in proxy["username"]:
        proxy["username"] = proxy["username"].replace(
            "{session}", secrets.token_hex(6)
        )
    return proxy


async def _resolve_proxy(session: str | None, retry: int) -> dict | None:
    """IPRoyal first, fall back to generic pool."""
    iproyal = _iproyal_proxy(session, retry)
    if iproyal:
        return iproyal
    return await _next_pool_proxy()


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
    session: str | None = None,
    retry: int = 0,
) -> str:
    """Fetch a URL with JS rendering. Returns fully rendered HTML.

    session: sticky key for IPRoyal — same session -> same residential IP.
             Use the manufacturer slug for per-brand stickiness.
    retry:   increment to rotate to a fresh IP within the same session family.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return ""

    proxy = await _resolve_proxy(session, retry)

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
                    await page.wait_for_selector(wait_selector, timeout=5000)
                else:
                    await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            html = await page.content()
            return html
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
