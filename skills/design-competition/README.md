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
| `run-harness.sh` | L10 loop entrypoint (`MODE=auto\|human`) |
| `capture-shots.sh` | shared pinned screenshot capture @ 1440/768/375 |
| `contact-sheet.sh` | L3 best-of-N contact sheet |
| `loop-config.yaml` | L7 iteration caps / stop conditions (all caps unverified) |
| `check-conformance.sh` | **proves** the contracts connect (C1–C6) |
| `validate-critique.sh` · `assert-evidence.sh` · `render-baton-md.sh` · `human-seat-to-json.sh` | helpers the loop calls |

## Verify it yourself
```sh
scripts/check-conformance.sh   # C1, C2, C2b, C3–C6
```
The checks prove **schema closure** (C1), **wrapper-canonicalization determinism on a staged payload**
(C2 — *not* live-seat byte-identity), **closed seat channels** (C2b: jq rejects named seat keys, ajv
also rejects novel keys in `per_criterion`), **schema validation** (C3), the **single feedback baton**
(C4), the **viewport pin** (C5), and the **rubric direction** (C6). They do **not** prove that two
independent judges emit identical bytes or equivalent scores — that is the chief open risk below.

## Preconditions to run a real loop
- A target git project **with at least one commit** (`run-harness.sh` derives its run id from `HEAD`,
  and the harness diffs/merges via git worktrees).
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
