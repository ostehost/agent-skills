# Generator–Evaluator Design Harness — REFINED Specification (Architect, blocking-fix pass)

This supersedes the prior refined spec. It addresses the three blocking issues:
(1) **the scaffold files physically exist on disk** (incl. `generator.md`, `supervisor.md`, and the helper/validator/conformance scripts the loop actually calls); (2) **the baton / viewport / rubric / schema-closure contracts are machine-checked** by `check-conformance.sh` against the real files — but the swappable seat is **structural alignment + normalization, NOT a proof of indistinguishability** (see §1 invariant 1 and §17 C2); (3) **the evidence ledger gap is closed** — the Deque coverage report, axe-core #4415, and the two Playwright MCP pages are now in `RESEARCH-LOG.md` with verbatim quotes (re-confirmed via WebFetch), and the log's WCAG reference is corrected to 2.2 AA.

> **V&V pass (independent review applied).** This revision applies the independent V&V findings: B1 (this honest re-scoping of the seat "proof"), B2 (missing agents shipped; dangling `SCORES.md`→`scores.csv`; axe pinned `4.12.1`), B3 (§16 now documents judge gameability + validity), and majors M1–M5 (cross-family/length-neutral judging; schema-enforced seat-blindness via a single-sourced forbidden list + closed `per_criterion`; vision+code judging; current-anchored feedback; Playwright reclassified first-party). See §16 and the per-file changelog.

Read §1 (invariants), §2 (Resolution Register), §17 (conformance — NEW, the proof the contracts connect), and §16 (genuinely-remaining mismatches) first. §4–§14 are the per-lane spec. §15 is the evidence ledger.

The honest headline: the gated artifact is **structurally aligned** across seats — seat-correlated statistics live in a loop-blind sidecar, the schema is closed on every object (incl. `gate.per_criterion`), a single-sourced forbidden-key list is stripped by the wrapper, and the loop-visible score is quantized onto a 0.5 grid both seats can emit. This **normalizes** the two seats; it does **not prove they are indistinguishable**. Free-text fields (`rationale`, `change_requests[].*`) can still carry a seat watermark, and two independent judges will not emit byte-identical output in practice. **Real-seat byte-identity and cross-seat score-equivalence (κ) are UNVALIDATED and must be measured on the calibration gold set.** §17 C2 proves only that the wrapper's canonicalization is *deterministic on a staged identical payload*; C2b proves the structural seat *channels* are closed. We make the residual differences explicit (sidecar + §15 + §16) rather than hiding them.

---

## 0. Terminology (invariant 6)
- **Single-track** = "generator–evaluator (GAN-style) harness": one direction, 5–15 sequential refine/pivot iterations (VERIFIED Anthropic loop).
- **Parallel** = "best-of-N candidate selection (pairwise LLM-as-judge)": N diverse candidates screened/selected comparatively.
- "Design competition" = informal shorthand only; never in code/artifacts.

## 0.1 Implementation status (this pass)
All files in §3 marked `[on disk]` exist under the project root. `bash -n` passes on all 8 shell scripts; `jq -e .` passes on all 4 JSON files; `./check-conformance.sh` returns **ALL CONFORMANCE CHECKS PASSED** (§17). ajv, ImageMagick `montage`, and Playwright/Chromium are external deps NOT installed on the authoring box — scripts degrade with explicit errors and the validator falls back to a jq-only checker so the loop is runnable on a stock machine.

---

## 1. Shared invariants as enforced contracts

| # | Invariant | True-by-construction enforcement | Conformance gate |
|---|---|---|---|
| 1 | **Swappable seat (structural, not proven-equivalent)** | Both seats emit the same closed schema on an identical 0.5 grid; the wrapper strips a single-sourced forbidden-key list (`schemas/forbidden-keys.txt`) and canonicalizes via `jq`. Schema is closed (`additionalProperties:false` at root/scores/scoreObj/changeRequest **and `gate.per_criterion`**, M2) so a seat *property* is unrepresentable — **but free text can still carry a watermark, so this is normalization, not a proof of indistinguishability**. Seat-correlated data → `critique-<k>.audit.json`. **κ / real-seat byte-identity UNVALIDATED (§16).** | §17 C1+C2+C2b |
| 2 | **Shared baton** | Exactly one loop-read file: `NEXT_FINDINGS.json`. Loop branches via `jq -r '.verdict'`. The generator prompt reads only that file. | §17 C4 |
| 3 | **Fixed viewports + pinned capture** | Widths 1440/768/375; heights pinned 900/1024/812 (unverified default) in `capture-shots.sh`. Screenshots captured ONCE per round by the shared pinned step, not by either seat ⇒ evidence pixels byte-identical across seats. | §17 C5 |
| 4 | **Four-criterion rubric** | `design_quality, originality, craft, functionality`; VERIFIED weight **direction** design+originality **over** craft+functionality, asserted in `rubric.json.weight_direction`. Exact weights/scale/thresholds (unverified), owned by L5. | §17 C6 |
| 5 | **Selection keeps-all** | Every iteration/candidate artifact kept forever; best chosen across all comparatively; pointwise never eliminates on quality (only the objective floor gates). | — |
| 6 | **Terminology** | As §0. | — |
| 7 | **Evidence discipline** | Every numeric (unverified) unless §15 + `RESEARCH-LOG.md` give a real source. axe coverage / Playwright vision / WCAG 2.2 now traced in the log. | §15 |
| **8** | **Vision + code judging (M3)** | BOTH the pinned screenshot AND the candidate's code/DOM MUST be in the judging context. Design_quality/originality cannot be scored from DOM alone; **craft cannot be scored from the screenshot alone** — withholding code hurts a web-UI judge more than withholding screenshots (WebDevJudge). Evaluator/generator models MUST be multimodal **and cross-family** (M1). | §15 (Playwright), §16#9 |

---

## 2. Resolution Register (unchanged from prior refined pass; summarized)

C3' (drop seat identity + all seat-correlated stats from the gated artifact → sidecar; quantize auto EV to the 0.5 grid), C5' (1–5 on 0.5 grid both seats), C7 (evaluator+capture wrapper-owned, evaluator never writes files), C8 (never stop on PASS), C10' (axe floor is explicitly PARTIAL; human 43%-class findings are advisory change_requests, never floor keys), R-VISION (M1/inv 8), R-INJECTION (M2: page untrusted, `browser_evaluate` runs only the pinned axe script, page text quarantined, gate recomputed deterministically), R-UNRENDERABLE (M3), R-NOVELTY (M4: perceptual diff over rendered shots), R-HEADLESS-FLOOR (M6), R-CONFIDENCE (M7: confidence advisory, removed from gating), X1' (PreToolUse hooks authoritative; Stop hook optional non-authoritative backstop), X2' (`weighted_total` single name, penalty-consistent example), X3' (only mode branch = which evaluator to invoke), X4' (`recommendation` enum = refine|pivot). All stand and are now *embodied in files*, not just prose.

---

## 3. Canonical run layout (files marked [on disk] now exist)
```
project/
├── DESIGN.md                       [on disk] L0 frozen brief
├── BRIEF.yaml                      [on disk] L1 intent/aesthetic/gate/constraints
├── tokens/primitives.tokens.json   [on disk] L0 FROZEN DTCG 2025.10 OKLCH
├── rubric.json                     [on disk] L5 criteria/weights/floor/axe_core_version/grid + weight_direction assertion
├── rubric.md                       [on disk] L5 human-readable + few-shot anchor placeholders
├── schemas/critique.schema.json    [on disk] L6 gated contract (draft 2020-12) — seat-blind, closed
├── loop-config.yaml                [on disk] L7 caps/stop conditions (all unverified)
├── run-harness.sh                  [on disk] L10/X wrapper + loop (SDK-less fallback)
├── capture-shots.sh                [on disk] shared pinned capture (NOT a seat)
├── contact-sheet.sh                [on disk] L3 best-of-N montage
├── check-conformance.sh            [on disk] NEW: proves the contracts (§17)
├── validate-critique.sh            [on disk] NEW: jq-only schema fallback (ajv-compatible call shape)
├── assert-evidence.sh              [on disk] NEW: evidence files must exist on disk
├── render-baton-md.sh              [on disk] NEW: derive human mirror from baton
├── human-seat-to-json.sh           [on disk] NEW: human REVIEW-SHEET → identical gated JSON
├── templates/{NEXT_FINDINGS.json,NEXT_FINDINGS.md,FINDINGS.md}  [on disk]
├── calibration/{anchors.jsonl,agreement.json}   (gold-set; fill from real data)
├── .claude/agents/evaluator.md     [on disk] L4a auto seat (write-locked, multimodal, injection-hardened)
└── runs/<run_id>/                  (created at runtime)
    ├── RUN_MANIFEST.json events.jsonl scores.csv budgets.json STOP_REASON
    ├── NEXT_FINDINGS.json          THE baton (loop-read). NEXT_FINDINGS.md = derived mirror (never read).
    └── candidates/<cid>/round-<n>/
        ├── build/ shots/{1440,768,375}.png      (SHARED pinned capture)
        ├── critique-<k>.json                     gated, seat-blind, byte-identical
        ├── critique-<k>.audit.json               SIDECAR (loop-blind): EV, samples, stdev, eval_steps, bias, seat
        └── merged.json                           reconciliation → derives baton
```

---

## 4–14 (per-lane spec — unchanged from prior refined pass)
L0 substrate (DTCG 2025.10 OKLCH, frozen primitives, seat-agnostic `check-conformance.sh`); L1 brief (`BRIEF.yaml`, vision-grounded `reference_images` required); L6 interchange schema (the seat-blind gated artifact — now realized in `schemas/critique.schema.json`); L4 evaluator seats (one contract `.claude/agents/evaluator.md`, two implementations, screenshots consumed not captured); L5 rubric (`rubric.json` carries the verified DIRECTION + unverified numbers + pinned `axe_core_version`); L2 generator (two-pass plan-then-build, reads exactly one baton); L3 best-of-N fan-out (optional, contact-sheet via `contact-sheet.sh`, keeps all); L7 iteration control (`loop-config.yaml`, P1 schema / P2 weight-direction / P3 axe-version preconditions, perceptual novelty, no confidence-gating); L8 selection (pointwise floor-gate then comparative over the whole floor-passing pool, R-HEADLESS-FLOOR for empty pools); L10 orchestration (single `MODE` flag = which evaluator to invoke); X guardrails (single wrapper persists critique bytes + shared capture; R-INJECTION). See the prior refined spec body for full text; the substantive change in this pass is that each lane's artifact now exists and is conformance-checked.

---

## 15. Consolidated VERIFIED ⟷ (unverified) ledger (now traceable in RESEARCH-LOG.md)
**VERIFIED (each with a source in `RESEARCH-LOG.md`):** four-criterion design rubric + verbatim defs; weight DIRECTION design+originality > craft+functionality; per-criterion hard-threshold gate (Anthropic **coding** harness only); 5–15 iterations; calibration few-shots reduce drift; agents over-grade own work; middle iteration often preferred; the three SKILL.md AI clusters + slop tells + "boldness in one place"; two-pass plan-then-build; generator decides refine/pivot from trend; DTCG 2025.10 color object form + OKLCH; Tailwind v4 `@theme`; design.md alpha (pin commit); **WCAG 2.2 AA current W3C Rec + 4.5:1/3:1** (log updated from 2.1); **axe-core ~57% automated / ~43% manual — floor necessarily PARTIAL** ([Deque report](https://www.deque.com/automated-accessibility-coverage-report/): "57.38% of total issues were identified using Deque's automated tests"; [axe-core #4415](https://github.com/dequelabs/axe-core/issues/4415): "you can find on average 57% of WCAG issues automatically"); **Playwright vision capability** ([capabilities](https://playwright.dev/mcp/capabilities): `--caps=vision` = "Coordinate-based mouse tools for screenshot-driven workflows. Requires a vision-capable LLM"; [vision-mode](https://playwright.dev/mcp/vision-mode): default uses accessibility snapshots) — confirming omitting `--caps=vision` still returns screenshots, only dropping coordinate-click tools; SimpleStrat/Verbalized Sampling; pairwise position & self-preference bias + mitigations; GenSelect/knockout/round-robin theory (math domain); pointwise-weak-at-selection (best-of-2); SDK `structured_output`/`ResultMessage`/caps; Stop-hook parallel/no-order; headless MCP not auto-approved.
**(unverified) — never ship as fact:** all weights, scale (1–5), 0.5-grid choice, thresholds, floors, penalties, caps, N, concurrency, plateau-K, κ band, budgets; per-criterion-gate→**design** transfer; G-Eval/ensembles/separate-calls as Anthropic practice; token-conformance bridge; OKLCH stepping curve; BRIEF.yaml key set; fan-out-beats-single-track (central L3 bet); selection-theory transfer to frontend; CRDAL/novelty/Reflexion transfer; perceptual-novelty thresholds; **human-0.5-grid ↔ auto-quantized-EV κ-comparability (chief inter-seat risk)**; whether quantizing auto EV materially hurts loop/selection quality.

---

## 16. Genuinely-remaining mismatches
1. **κ across the two value distributions (CHIEF inter-seat risk).** The seats are structurally aligned (§1 inv 1), but **byte-identity of two LIVE seats is NOT achieved** — only staged-payload canonicalization is (§17 C2). Auto (quantized EV) and human (0.5-grid) may also produce different score *distributions*. No empirical κ for this domain; `calibration/agreement.json` must measure it before any cross-seat comparison is trusted. **Structural interchangeability ≠ proven score-equivalence.**
2. **Quantization tradeoff.** Forcing auto onto the grid may degrade ranking vs full EV. Unmeasured; A/B it. (Cost/benefit may be inverted — you pay resolution for a byte-identity that won't materialize on live seats; reconsider quantizing at all.)
3. **R-INJECTION residual.** Quarantining page text does not eliminate vision-channel injection via the screenshot the multimodal judge must view. Untested. (Bounded: the floor gate is recomputed deterministically from the pinned axe script, so injection can only move non-gating aesthetic scores.)
4. **design.md alpha drift.** Pin check cannot detect same-SHA semantic spec changes.
5. **Human pairwise non-transitivity (L8).** Bites only the *optional* fan-out (L3/L8); the single-track default has no pool to aggregate. Mixing transitive (auto) + non-transitive (human) preferences across a pool is policy, not formalized math.
6. **Validator parity.** The jq fallback enforces only a load-bearing SUBSET (named-key seat-blindness, grid, enums-by-hand) and **disagrees with ajv in both directions** — it accepts unknown top-level keys / bad enums that ajv rejects, and rejects duplicate-viewport arrays ajv accepts. **ajv is AUTHORITATIVE; the jq path is a stock-box fallback only.** Seat-blindness's *structural* half now lives in the closed schema (M2), not only the jq grep; run ajv in CI.
7. **Reward hacking / optimizing against the judge (B3).** The loop refines the generator against the evaluator and **selects on the evaluator's score**; an imperfect proxy can have its ratings rise while true quality stalls or drops (Pan et al. 2024, *Spontaneous Reward Hacking in Iterative Self-Refinement*, arxiv 2407.04549; corroborating: null-model AlpacaEval 2410.07137; One-Token-to-Fool 2507.08794). **Mitigation in place:** the fresh-context evaluator kills Pan et al.'s dominant *shared-context* driver. **Still owed:** make the selection/stop signal partly INDEPENDENT of the optimization signal — a cross-family judge and/or a human spot-check of the *selected* artifact — and bound generator context to limit the length-driven variant (#11).
8. **Judge validity, not just reliability (B3).** §17 proves stability (schema/closure/determinism), never correctness. A judge can be perfectly swap-consistent and **systematically wrong** (JudgeBench, ICLR'25, arxiv 2410.12784 — strong judges near random on hard pairs). **Add a validity gate:** periodic human-vs-judge agreement on a held-out gold set (`calibration/agreement.json`, currently empty) plus a mandatory human spot-check on the selected winner before ship. WebDevJudge (2510.18560) puts best automated judge ~70% vs ~84% human — do not treat the score as ground truth.
9. **Self-preference / same-family bias (M1).** Generator and evaluator are likely the same family; self-preference tracks self-recognition (Panickssery 2404.13076) and familiarity/low-perplexity regardless of authorship (Wataoka 2410.21819). **Default to a cross-family evaluator; the k=3 panel MUST be cross-family** (a jury beats same-model self-consistency and is cheaper — Verga 2404.18796). Lock both model IDs in `RUN_MANIFEST.json`.
10. **Length / verbosity bias (M1).** Position-swap does not neutralize it (Length-Controlled AlpacaEval 2404.04475). The rubric + evaluator now carry a length-neutral clause; verify it holds empirically.
11. **Feedback-accumulation degradation (M4).** Carrying the full critique transcript degrades output and lengthens context (worsening #7). The baton (`NEXT_FINDINGS.json`) is overwritten each round so feedback is **current-anchored, not accumulated**; the generator also carries a markup/CSS bloat guard. Most refinement gain arrives in ~3 cycles against the 5–15/ceiling-20 budget (In-Place Feedback 2510.00777; *Another Turn, Better Output?* 2509.06770) — justify the ceiling against diminishing returns.

---

## 17. Conformance — what the checks actually demonstrate (re-scoped per V&V)
`./check-conformance.sh` runs against the actual files. **Read each check as the narrow thing it proves — not as proof of seat indistinguishability** (see §1 inv 1, §16#1):

- **C1 — schema structurally seat-blind.** Asserts `additionalProperties:false` on root + `scores` + `scoreObj` + `changeRequest` **and `gate.per_criterion`** (M2 — previously the one open object), and greps the schema for any DECLARED forbidden *property* using the single-sourced `schemas/forbidden-keys.txt`. This makes a seat *property* unrepresentable. It does **not** police seat watermarks in free-text values — that is fundamentally out of schema scope.
- **C2 — wrapper canonicalization determinism (STAGED, not live seats).** Routes ONE shared gated payload through the AUTO path (`structured_output` → `jq`) and the HUMAN path (REVIEW-SHEET embedding the SAME payload + stray seat keys → `human-seat-to-json.sh` strips them via the shared list → `jq`). `cmp -s` confirms byte-identity. **Because both paths start from one input by construction, this proves the wrapper is deterministic — NOT that two independent judges emit identical bytes.** Live-seat byte-identity and score κ are unvalidated (§16#1).
- **C2b — seat channels closed (adversarial regression).** Encodes the V&V probes: the jq validator REJECTS a named seat key inside `per_criterion`; with ajv present, the schema also REJECTS a novel key there. Free-text watermarks remain unpoliceable by design — stated, not hidden.
- **C3 — both validate.** ajv when installed (authoritative); else the jq subset (`validate-critique.sh`: grid, four criteria, verdict/severity enums, UNRENDERABLE-only null rule, single-sourced seat-key ban). **The two disagree in both directions (§16#6); ajv governs in CI.**
- **C4 — single FEEDBACK baton.** The generator's feedback comes only from `NEXT_FINDINGS.json`; its block references no `*.audit.json`, `NEXT_FINDINGS.md`, or deprecated `FINDINGS.md`. (It still legitimately reads DESIGN/BRIEF/tokens/`scores.csv` — those are inputs, not the feedback baton.)
- **C5 — viewports pinned.** `capture-shots.sh` pins `[1440,900],[768,1024],[375,812]` and the schema's `viewports.items.enum == [1440,768,375]`. Shared pinned capture ⇒ both seats consume identical pixels within a run.
- **C6 — rubric weight direction.** `weight_direction.verified == true`, assertion matches design+originality > craft+functionality, numeric weights satisfy `(0.35+0.35) > (0.20+0.10)`, and `_unverified` flags the numbers.

This is the artifact the SHIP-CHECK re-runs; it converts the prose-only structural contracts into a reproducible pass/fail. It does **not** substitute for the empirical κ / validity gate (§16#1, #8).
