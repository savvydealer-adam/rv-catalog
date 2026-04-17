"""Stealth fetcher — subprocess bridge to scripts/stealth/stealth_fetch.js.

Used for WAF-blocked OEM sites (Cloudflare/Akamai) where Playwright +
residential proxy gets HTTP 403. The Node side runs puppeteer-real-browser
(rebrowser-patched puppeteer-core + ghost-cursor + Turnstile auto-solve)
against Chrome on the local PC. Real residential IP + real Chrome fingerprint
together bypass WAF fingerprinting.

No proxy is used — this assumes the scraper runs on a trusted workstation
(not Cloud Run).

Env vars (all optional):
  STEALTH_NODE             path to node binary (default: "node")
  STEALTH_SCRIPT           absolute path to stealth_fetch.js
  STEALTH_HEADLESS         set to "1" to launch Chrome headless
  STEALTH_TIMEOUT_MS       default nav timeout (default: 60000)
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

_DEFAULT_SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts" / "stealth" / "stealth_fetch.js"
)


def _script_path() -> Path:
    override = os.getenv("STEALTH_SCRIPT", "").strip()
    if override:
        return Path(override)
    return _DEFAULT_SCRIPT


def stealth_available() -> bool:
    """True when the Node CLI exists on disk."""
    return _script_path().is_file()


async def stealth_fetch(
    url: str,
    wait_selector: str | None = None,
    timeout_ms: int | None = None,
    networkidle: bool = False,
    settle_ms: int = 1500,
) -> str:
    """Fetch a URL via puppeteer-real-browser. Returns rendered HTML or ''."""
    script = _script_path()
    if not script.is_file():
        return ""

    node = os.getenv("STEALTH_NODE", "node")
    headless = os.getenv("STEALTH_HEADLESS", "").strip() == "1"
    nav_timeout = int(timeout_ms or os.getenv("STEALTH_TIMEOUT_MS", "60000"))

    cmd: list[str] = [node, str(script), url,
                      f"--timeout={nav_timeout}",
                      f"--settle={settle_ms}"]
    if wait_selector:
        cmd.append(f"--wait-selector={wait_selector}")
    if networkidle:
        cmd.append("--networkidle")
    if headless:
        cmd.append("--headless")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(script.parent),
        )
        try:
            stdout_b, _ = await asyncio.wait_for(
                proc.communicate(), timeout=(nav_timeout / 1000) + 60
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            return ""
    except FileNotFoundError:
        return ""
    except Exception:
        return ""

    if not stdout_b:
        return ""

    try:
        payload = json.loads(stdout_b.decode("utf-8", errors="replace"))
    except Exception:
        return ""

    if not isinstance(payload, dict):
        return ""
    if payload.get("error"):
        return ""
    status = payload.get("status")
    if status and int(status) >= 400:
        # Still return the HTML — a 404/500 body can still be useful for
        # catching redirects and diagnostics — but many callers will discard it.
        return payload.get("html") or ""
    return payload.get("html") or ""
