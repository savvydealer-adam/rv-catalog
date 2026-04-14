"""Playwright-based page fetcher for JS-heavy sites."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

try:
    from playwright.async_api import async_playwright, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


_browser_lock = asyncio.Lock()
_browser: "Browser | None" = None


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


async def render_page(url: str, wait_selector: str | None = None, timeout_ms: int = 20000) -> str:
    """Fetch a URL with JS rendering. Returns fully rendered HTML."""
    if not PLAYWRIGHT_AVAILABLE:
        return ""

    async with _shared_browser() as browser:
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 720},
        )
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            # Give SPAs a moment to hydrate
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
    global _browser
    if _browser is not None:
        try:
            await _browser.close()
        except Exception:
            pass
        _browser = None
