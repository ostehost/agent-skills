#!/usr/bin/env bash
# Shared pinned capture. Both seats cite these byte-identical screenshots as evidence.
# Pin EVERYTHING that changes pixels: engine build, DPR, fonts, color-scheme, motion.
set -euo pipefail
URL="${1:?url}"; OUT="${2:?outdir}"; mkdir -p "$OUT"
# Heights are UNVERIFIED defaults; pin them so Auto and Human evidence match.
node -e '
const { chromium } = require("playwright");
const url = process.argv[1], out = process.argv[2];
const vps = [[1440,900],[768,1024],[375,812]];
(async () => {
  // pin the browser build via PLAYWRIGHT_BROWSERS_PATH + a locked playwright version in package.json
  const browser = await chromium.launch({ headless: true });
  for (const [w,h] of vps) {
    const ctx = await browser.newContext({
      viewport: { width: w, height: h },
      deviceScaleFactor: 1,
      reducedMotion: "no-preference",   // pinned; reduced_motion is a separate optional floor key
      colorScheme: "light"
    });
    const page = await ctx.newPage();
    await page.goto(url, { waitUntil: "networkidle", timeout: 15000 });
    await page.screenshot({ path: `${out}/${w}.png`, fullPage: false });
    await ctx.close();
  }
  await browser.close();
})().catch(e => { console.error("CAPTURE_FAILED", e.message); process.exit(3); });
' "$URL" "$OUT"
