# Design Competition Harness

A frontend **generator–evaluator (GAN-style) harness** that generates a design, scores it against a
rubric, feeds critique back, and iterates until it converges — runnable in two **interchangeable**
modes: **Human** (a person judges) and **Auto/Playwright** (an AI evaluator judges a live page).
Only the evaluator seat swaps; everything else is shared. The seats are **structurally aligned**
(one gated schema, one normalization wrapper, one baton) — not *proven* equivalent: see Open risks.

> Built without reinventing the wheel: grounded in Anthropic's published harness + the practitioner
> human-in-the-loop layer, then refined by a 12-lane research/review/verify swarm. Every claim is
> tagged **VERIFIED** (with a source) or **(unverified)** — see `RESEARCH-LOG.md`.

## Read in this order
1. **`WORKFLOW.md`** — the canonical layered spec (L0–L10) + shared vocabulary. Start here.
2. **`HARNESS.md`** — the refined, implementable spec: enforced invariants, resolution register,
   conformance section, and the genuinely-remaining mismatches.
3. **`RESEARCH-LOG.md`** — citation-backed findings for all 10 gaps + the rejected-claims appendix.

## Scaffold (runnable)
| File | Role |
|---|---|
| `DESIGN.md` | L0 frozen design brief (the shared "why" + semantic rules) |
| `tokens/primitives.tokens.json` | L0 frozen DTCG token primitives (exact values) |
| `BRIEF.yaml` | L1 brief/intent template |
| `.claude/agents/generator.md` | L2 generator subagent (two-pass plan→build, current-anchored feedback) |
| `.claude/agents/evaluator.md` | L4a Auto evaluator subagent (write-locked, Playwright, cross-family, vision+code) |
| `.claude/agents/supervisor.md` | L7 CRDAL anti-fixation supervisor (optional; writes only STEER.md) |
| `rubric.json` / `rubric.md` | L5 four-criterion rubric (verified direction; numbers labeled unverified) |
| `schemas/critique.schema.json` | L6 **seat-blind** gated critique schema (closed objects incl. `per_criterion`) |
| `schemas/forbidden-keys.txt` | single source of the banned seat-key list (M2; used by 3 scripts) |
| `templates/NEXT_FINDINGS.json` | THE baton (the only file the loop reads) |
| `templates/NEXT_FINDINGS.md` | derived human mirror (never read by the loop) |
| `templates/mcp.json` | pinned Playwright MCP server config (copied into each round dir in Auto mode) |
| `templates/REVIEW-SHEET.md` | canonical blank human-seat form (rendered per round in Human mode) |
| `scripts/run-harness.sh` | L10 loop entrypoint (`MODE=auto\|human`) |
| `scripts/capture-shots.sh` | shared pinned screenshot capture @ 1440/768/375 |
| `scripts/contact-sheet.sh` | L3 best-of-N contact sheet |
| `loop-config.yaml` | L7 iteration caps / stop conditions (all caps unverified) |
| `scripts/check-conformance.sh` | **proves** the contracts connect (C1–C8) |
| `scripts/validate-critique.sh` · `scripts/assert-evidence.sh` · `scripts/render-baton-md.sh` · `scripts/human-seat-to-json.sh` | helpers the loop calls |

## Verify it yourself
```sh
scripts/check-conformance.sh   # C1, C2, C2b, C3–C8
```
The checks prove **schema closure** (C1), **wrapper-canonicalization determinism on a staged payload**
(C2 — *not* live-seat byte-identity), **closed seat channels** (C2b: jq rejects named seat keys, ajv
also rejects novel keys in `per_criterion`), **schema validation** (C3), the **single feedback baton**
(C4), the **viewport pin** (C5), the **rubric direction** (C6), the **pinned Auto-seat MCP config**
(C7: `templates/mcp.json` ships version-pinned and the loop materializes it before
`--strict-mcp-config` reads it), and the **runnable preconditions** (C8: the loop installs the
subagents into the target project; Human mode renders the REVIEW-SHEET and blocks for it). They do
**not** prove that two independent judges emit identical bytes or equivalent scores — that is the
chief open risk below.

## Preconditions to run a real loop
- A target git project **with at least one commit** (`run-harness.sh` derives its run id from `HEAD`,
  and the harness diffs/merges via git worktrees).
- The candidate app already **served on `http://localhost:$PORT`** (default 4173) — the harness
  captures and evaluates a live page; it does not start your dev server.
- Subagents and the Auto-seat MCP config need **no manual setup**: `run-harness.sh` copies
  `.claude/agents/{generator,evaluator,supervisor}.md` into the target project's `.claude/agents/`
  at startup and `templates/mcp.json` (pinned `@playwright/mcp@0.0.78`, latest as of 2026-07-28)
  into each round dir before invoking the evaluator.
- External deps for a live run: `npm i -g ajv-cli` (the scaffold calls it with **`--spec=draft2020`** —
  required, or ajv rejects the 2020-12 schema wholesale), `brew install imagemagick`, `npx playwright
  install chromium` (a pinned Playwright version for byte-stable screenshots). Scripts degrade with
  clear errors and a jq-only validator fallback when these are absent.
- **ajv is authoritative** for schema validation; the jq fallback enforces only a load-bearing subset
  and disagrees with ajv in both directions — run ajv in CI. (Verified: with `--spec=draft2020`, ajv
  accepts a valid critique and rejects novel `per_criterion` keys, bad enums, and unknown top-level
  keys — the structural seat channels are genuinely closed; only free-text watermarks remain
  unpoliceable, by design.)

## Open risks (see `HARNESS.md` §16 for full text)
The swappable seat is **structural alignment + normalization, NOT a proof of indistinguishability**:
free-text fields can still carry a seat watermark, and two independent judges will not produce
byte-identical output — so real-seat byte-identity and **cross-seat score-equivalence (κ) are
UNVALIDATED** and must be measured on the calibration gold set. The loop also **optimizes a generator
against a judge and selects on that judge's score**, so it inherits the LLM-as-judge failure modes:
reward hacking / eval-gaming, judge *validity* (a swap-consistent judge can be systematically wrong —
add a human spot-check + held-out agreement gate), same-family self-preference, and length bias.
Lower-level: grid-quantization may cost ranking resolution, the jq validator is a subset of
draft-2020-12 (ajv is authoritative), vision-channel prompt-injection residual, human
non-transitivity aggregation is prose-only, and `design.md` is alpha.

## Prior art & why this implementation exists
This harness re-implements a published pattern rather than adopting an existing package — a
documented decision, not an oversight. The known alternatives:

- **`gan-style-harness`** ([affaan-m/everything-claude-code](https://github.com/affaan-m/everything-claude-code/blob/main/skills/gan-style-harness/SKILL.md))
  — a public Claude Code skill shipping the same core: generator + write-separated Playwright
  evaluator, the same four weighted criteria (design quality / originality / craft /
  functionality), a feedback-file baton, and a ~15-iteration cap. Its loop **stops when a weighted
  score crosses a threshold** — exactly the stop-on-PASS anti-pattern this harness's L7/C8
  rejects (PASS is recorded, never terminal; selection is best-across-rounds). It also has no
  human seat, no seat-blind gated schema, no accessibility floor, and no evidence binding.
  *(Deltas read from its published SKILL.md, not re-verified against a pinned commit —
  (unverified) beyond the terminology sourcing in `RESEARCH-LOG.md` G9.)*
- **`adversarial-dev`** ([coleam00/adversarial-dev](https://github.com/coleam00/adversarial-dev))
  — a second public generator/evaluator implementation in the same class. *(Existence noted;
  feature overlap (unverified).)*
- **`anthropics/cwc-long-running-agents`** — the upstream event demo this pattern derives from;
  explicitly unmaintained ("read and cherry-pick"), so wrapping it was never a maintained option.

What exists here and in none of the alternatives above — the reason this implementation is
maintained: the swappable **Human/Auto seat** behind one seat-blind gated critique schema
(`schemas/critique.schema.json` + `scripts/human-seat-to-json.sh`), ajv/jq schema gating, the
axe-core accessibility floor, cross-family anti-bias controls (`rubric.json.anti_bias`),
evidence binding to on-disk artifacts (`scripts/assert-evidence.sh`), and no-stop-on-PASS
best-across-rounds selection. Naming the overlap here also serves the judge-gameability
positioning (V&V B3): a judge-score stop condition is a reward-hacking surface, which is why
this harness refuses it.

## Independent V&V status (review of 2026-06-28)
`INDEPENDENT-VV-REVIEW.md` verdict: **SOUND-WITH-CORRECTIONS — not ready until 3 blockers
close.** Disposition as of 2026-07-28 (recorded here so the open verdict is never silently
promoted over):

- **B1 — swappable-seat "machine-proven" claim overstated:** corrected as a claims fix, not new
  proof machinery. C2 is now explicitly labeled a *staged-fixture wrapper-canonicalization
  determinism* proof (see ¶1 above, HARNESS §1/§17); live-seat byte-identity and cross-seat κ
  remain UNVALIDATED and are listed under Open risks. **Closed (wording).**
- **B2 — runnable scaffold could not run a round:** the loop now installs the subagents into the
  target project, ships and materializes the pinned Playwright MCP config, renders/blocks on the
  human REVIEW-SHEET, and fails loudly on CLI errors; conformance C7/C8 pin these. The axe-core
  version is pinned in `rubric.json` (4.12.1). **Closed mechanically; no full end-to-end run has
  been recorded yet — (unverified) until one is.**
- **B3 — judge-gameability/validity literature absent:** partially addressed — HARNESS §16 now
  carries the judge-validity limits with sources (JudgeBench 2410.12784; WebDevJudge 2510.18560),
  Open risks above states the reward-hacking/eval-gaming inheritance, and the prior-art section
  positions the design against score-threshold stopping. The validity *gate* itself
  (`calibration/` gold set + `agreement.json`) is still empty. **Open until calibration data
  exists.**
