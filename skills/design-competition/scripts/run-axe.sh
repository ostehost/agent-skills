#!/usr/bin/env bash
# Pinned axe-core oracle (the machine-computed quality floor). Runs the axe-core
# resolved from WORKDIR's node_modules (pin axe-core@<rubric.json axe_core_version>
# there, next to playwright) against URL at the three pinned viewports and writes
# axe-<w>.json into OUT. The evaluator READS these files; it never injects or runs
# page-suggested JS (R-INJECTION). Missing output files mean the floor keys fail
# closed for that viewport.
set -euo pipefail
URL="${1:?url}"; OUT="${2:?outdir}"; WORKDIR="${3:-$PWD}"
mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"
cd "$WORKDIR"
node -e '
const { chromium } = require("playwright");
const axe = require("axe-core");
const fs = require("fs");
const url = process.argv[1], out = process.argv[2];
const vps = [[1440,900],[768,1024],[375,812]];
(async () => {
  const browser = await chromium.launch({ headless: true });
  for (const [w,h] of vps) {
    const ctx = await browser.newContext({
      viewport: { width: w, height: h },
      deviceScaleFactor: 1,
      colorScheme: "light"
    });
    const page = await ctx.newPage();
    await page.goto(url, { waitUntil: "networkidle", timeout: 15000 });
    await page.evaluate(axe.source);
    const result = await page.evaluate(async () =>
      await axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] } })
    );
    fs.writeFileSync(`${out}/axe-${w}.json`, JSON.stringify({
      axe_core_version: result.testEngine.version,
      viewport: w,
      violations: result.violations
    }, null, 2));
    await ctx.close();
  }
  await browser.close();
})().catch(e => { console.error("AXE_FAILED", e.message); process.exit(3); });
' "$URL" "$OUT"
