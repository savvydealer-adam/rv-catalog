#!/usr/bin/env node
// Stealth URL fetcher for WAF-blocked OEM sites.
//
// Uses puppeteer-real-browser (rebrowser-puppeteer-core + ghost-cursor +
// Cloudflare Turnstile auto-solve). Runs non-headless from the local PC so
// the residential IP + real Chrome fingerprint together bypass Cloudflare
// and Akamai WAF.
//
// Usage:
//   node stealth_fetch.js <url> [--wait-selector=<css>] [--timeout=<ms>]
//                              [--networkidle] [--settle=<ms>] [--headless]
//
// Output (stdout, on success):
//   { "url": "...", "finalUrl": "...", "status": 200,
//     "title": "...", "html": "<!doctype html>..." }
//
// On failure, exit code 1 and a JSON error on stdout:
//   { "error": "...", "url": "..." }

const { connect } = require('puppeteer-real-browser');

function parseArgs(argv) {
  const args = { positional: [], flags: {} };
  for (const a of argv) {
    if (a.startsWith('--')) {
      const eq = a.indexOf('=');
      if (eq > -1) {
        args.flags[a.slice(2, eq)] = a.slice(eq + 1);
      } else {
        args.flags[a.slice(2)] = true;
      }
    } else {
      args.positional.push(a);
    }
  }
  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const url = args.positional[0];
  if (!url) {
    process.stdout.write(JSON.stringify({ error: 'missing url argument' }));
    process.exit(2);
  }

  const timeoutMs = Number(args.flags.timeout || 45000);
  const settleMs = Number(args.flags.settle || 1500);
  const waitSelector = args.flags['wait-selector'] || null;
  const waitNetworkIdle = !!args.flags.networkidle;
  const headless = !!args.flags.headless;

  let browser = null;
  let page = null;
  try {
    ({ browser, page } = await connect({
      headless,
      turnstile: true,
      disableXvfb: true,
      args: [
        '--window-size=1366,900',
        '--disable-blink-features=AutomationControlled',
      ],
      customConfig: {},
      connectOption: { defaultViewport: null },
    }));

    page.setDefaultNavigationTimeout(timeoutMs);

    const response = await page.goto(url, { waitUntil: 'domcontentloaded' });
    const status = response ? response.status() : 0;

    if (waitSelector) {
      try { await page.waitForSelector(waitSelector, { timeout: 15000 }); }
      catch (_) { /* best-effort */ }
    } else if (waitNetworkIdle) {
      try { await page.waitForNetworkIdle({ idleTime: 1000, timeout: 15000 }); }
      catch (_) { /* best-effort */ }
    }

    if (settleMs > 0) await new Promise(r => setTimeout(r, settleMs));

    const finalUrl = page.url();
    const title = await page.title().catch(() => '');
    const html = await page.content();

    process.stdout.write(JSON.stringify({
      url, finalUrl, status, title, html,
    }));
  } catch (err) {
    process.stdout.write(JSON.stringify({
      error: String(err && err.message || err),
      url,
    }));
    process.exitCode = 1;
  } finally {
    try { if (page) await page.close(); } catch (_) {}
    try { if (browser) await browser.close(); } catch (_) {}
  }
}

main();
