# Independent V&V — `design-competition/` Generator–Evaluator Harness

> **What this is.** A standalone, independent verification & validation review of the harness
> (README, WORKFLOW.md, HARNESS.md, RESEARCH-LOG.md + the runnable scaffold). It is **read-only
> feedback for the author** — it changes nothing in the harness, the scaffold, the verified/unverified
> tags, or git. All proposed wording in Appendix A is a *suggestion to apply*, not an applied edit.
>
> **Reviewer ownership.** Produced as an independent pass (not by the generating swarm). Hands-on
> fronts (contract scrutiny, risk reassessment, rejected-claims audit) done directly against the files;
> web-heavy fronts (source re-verification, 2026 completeness) done by three parallel verification
> agents whose fetched quotes are reproduced below.
>
> **Run / fetch date: 2026-06-28.** `check-conformance.sh` run locally; every load-bearing source
> re-fetched live the same day. Tooling present: `jq`, `cmp`, `node/npx`, `shellcheck`. Absent:
> `ajv`, `playwright`, `imagemagick` — so the jq-only validator path is what executes here, and any
> Playwright-dependent step is untested on this box. The marketing repo has **no commits yet**
> (everything staged) → there is no CI; "CI state" = local-only.

---

## 0. Overall recommendation: SOUND-WITH-CORRECTIONS — not ready for a final draft until 3 blockers close

The architecture is good and the **evidence base is genuinely clean** — every VERIFIED claim
re-fetched today HOLDS, no dead links, no VERIFIED claim has an unsupported source, and none of the
33 rejected claims was wrongly thrown out. RESEARCH-LOG.md is unusually disciplined (every number
marked, weak claims rejected, self-corrections).

The defects are concentrated where the harness's **own selling point is rigor**:

1. **B1 — the "swappable-seat is machine-PROVEN" claim overstates what the conformance suite shows.**
2. **B2 — the "runnable scaffold" cannot run a round** (missing agents, a dangling `SCORES.md`, a blank axe pin).
3. **B3 — for a loop that optimizes a generator against a judge and then *selects on that judge*, the 2024–2026 judge-gameability/validity literature is entirely absent.**

None require re-architecting. They require re-wording, three missing files, and a risk section. The
research log itself needs only a few date/citation fixes. **Net: fix B1–B3 (and ideally the majors)
before the final draft; the foundation is strong and the corrections are bounded.**

**Lineage confirmed.** The Anthropic post *is* single-track generator→evaluator (5–15 iterations,
not a parallel bake-off). "Design competition" as informal shorthand, and best-of-N as a community
layer *in front of* that loop, is correct — G9's terminology correction holds.

---

## 1. Prioritized findings

Severity is calibrated to "a spec + scaffold being **finalized**," not "production code being shipped."
Each item: claim → evidence (file:line and/or source) → fix.

### BLOCKERS — fix before the final draft

#### B1 — The swappable-seat "proof" overstates what is proven
`README.md:36-40` and `HARNESS.md §17` present C1/C2 as machine-VERIFIED ("the loop cannot tell which
seat produced it," `HARNESS.md:101`). Hands-on probes against the real files contradict the headline:

- **C2 byte-identity is staged by the fixture.** `check-conformance.sh:28-65` builds ONE `$GATED`
  object and routes the *same* object down both the "auto" and "human" paths; the human path only
  `del()`s a fixed key-list (`human-seat-to-json.sh:13`) and both paths end in `jq .`. `cmp -s` is
  therefore identical **by construction** — the check proves `jq` canonicalization is deterministic on
  identical input, **not** that two independent judges (a person and a multimodal model) emit identical
  bytes. Two real seats writing free-text rationales will essentially never be byte-identical.
- **Seat-blindness has live holes** (probes reproduced in §2.3). `additionalProperties:false` closes
  only the *named* objects. `gate.per_criterion` is an **open** object (`schemas/critique.schema.json:44`
  = bare `{"type":"object"}`), and every free-text field (`rationale`, `change_requests[].*`,
  `ai_slop_flags[]`, `rubric_ref`, …) can carry a seat watermark. A seat-distinguishing document is
  therefore schema-valid — so C1's "a seat key is *unrepresentable* in a schema-valid gated artifact"
  is false.

HARNESS.md:8 already half-concedes this ("byte-identity is necessary but not sufficient"), but the
README and §17 still present C2 as proof of indistinguishability. **The gap between the headline and
the proof is the single biggest credibility liability** because rigor is the selling point.

**Fix.** Reword the contract to what is true (Appendix A1): *shared gated schema + a wrapper that
strips a key-blocklist and canonicalizes via jq; real-seat byte-identity and score-equivalence are
UNVALIDATED.* Either close `gate.per_criterion` and accept that free text cannot be policed, **or**
(preferred — see §3) drop byte-identity as the contract entirely. Re-scope the §17 descriptions to
what each check actually demonstrates.

#### B2 — The "runnable" scaffold cannot run a round
`README.md:18` ("Scaffold (runnable)") and `:40` ("ALL CONFORMANCE CHECKS PASSED") oversell:

- **Missing agents.** `run-harness.sh:43` invokes `claude --agent generator` and `loop-config.yaml:24`
  references `agents/supervisor.md`, but `.claude/agents/` contains **only `evaluator.md`**. The
  generator and supervisor agent definitions are referenced, not shipped — the loop cannot generate.
- **Dangling `SCORES.md`.** The generator prompt (`run-harness.sh:44`) reads `SCORES.md` and decides
  refine/pivot "from SCORES.md trend" (`:48`), but the harness writes `scores.csv` (`:83`) and never
  `SCORES.md`. The **primary anti-fixation lever (refine vs pivot, the verified central control of
  G7) reads a file that is never created.**
- **Blank a11y floor.** `rubric.json:6` ships `axe_core_version: "REPLACE_PINNED_AXE_VERSION"` — a hard
  `quality_floor` gate whose ruleset is literally undefined. Current axe-core is **4.12.1** (4.12.0
  changed the active ruleset: added `aria-tab-name`, deprecated `landmark-complementary-is-top-level`).

**Fix.** Ship `generator.md` + `supervisor.md` (or remove the references and mark TODO); reconcile
`SCORES.md` ↔ `scores.csv`; pin axe `4.12.1`. Until then, soften the "runnable" / "ALL CHECKS PASSED"
framing.

#### B3 — Judge gameability AND validity are undocumented (the loop optimizes and selects on a judge it never checks)
The loop runs 5–15 (ceiling 20) generator iterations against the evaluator and L8 selects "best across
iterations" **by the evaluator's own score**. `HARNESS.md §16` ("genuinely-remaining mismatches")
names neither reward hacking nor validity. This is the textbook optimize-against-a-proxy setup.

- **Gameability.** Pan et al., *Spontaneous Reward Hacking in Iterative Self-Refinement*
  (https://arxiv.org/abs/2407.04549, 2024-07): "because the evaluator is an imperfect proxy of user
  preference, this optimization can lead to reward hacking, where the evaluator's ratings improve while
  the generation quality remains stagnant or even decreases as judged by actual human users." Its
  dominant driver is **shared context** — *your fresh-context evaluator already mitigates this; say so.*
  Corroborating: null-model AlpacaEval (https://arxiv.org/abs/2410.07137, ICLR'25 Oral — a constant
  non-answer scored 86.5% LC win); One-Token-to-Fool (https://arxiv.org/abs/2507.08794 — ":" elicits
  false-positive rewards).
- **Validity ≠ reliability.** §16/§17 only address κ and byte-identity (reliability/stability). Nothing
  checks whether the judge tracks ground-truth quality. A judge can be perfectly swap-consistent and
  systematically wrong — JudgeBench (https://arxiv.org/abs/2410.12784, ICLR'25): strong judges
  "performing just slightly better than random guessing" on hard pairs. The `calibration/agreement.json`
  slot exists but the directory is **empty**.

**Fix.** Add reward-hacking + validity to §16 (Appendix A2). Make the **selection/stop signal partly
independent** of the optimization signal — a cross-family judge and/or a human spot-check on the
*selected* artifact. Add a validity gate to calibration (periodic human-vs-judge agreement on a gold
set; the slot already exists). Credit the fresh-context evaluator as a real partial mitigation.

### MAJORS — should change the harness

- **M1 — Judge-bias controls are half-built.** You ban `self_preference` as a sidecar key but never
  require **judge ≠ generator family** (generator = Claude `frontend-design` plugin; evaluator almost
  certainly Claude too). Self-preference scales with self-recognition (Panickssery,
  https://arxiv.org/abs/2404.13076) and with familiarity/low-perplexity regardless of authorship
  (Wataoka, https://arxiv.org/abs/2410.21819). The `rubric.json:39` k=3 ensemble is **same-model
  self-consistency** — the wrong kind; a cross-family **panel** reduces intra-model bias *and* cost
  (Verga, *Replacing Judges with Juries*, https://arxiv.org/abs/2404.18796: "less intra-model bias…
  over seven times less expensive"). No **length/verbosity** neutrality either (position-swap doesn't
  touch it — Length-Controlled AlpacaEval, https://arxiv.org/abs/2404.04475).
  **Fix:** default to a cross-family evaluator; make the k=3 panel cross-family; add a length-neutral
  rubric clause; record/lock both seats' model IDs in the run manifest.

- **M2 — Validator parity is worse than §16#6 admits, with a dangerous inversion.** Probes (§2.3):
  `jq` **accepts** what ajv rejects (unknown top-level key; `recommendation:"banana"`;
  `weighted_total:"lots"`) **and rejects** what ajv accepts (duplicate viewports `[1440,1440,768]`).
  Critically, **seat-blindness is enforced only by the jq key-name grep** (`validate-critique.sh:15-16`,
  which scans key *paths*) — so "install ajv for full draft-2020-12 in CI" (the harness's own advice,
  `check-conformance.sh:75`) would **weaken** seat-blindness. The forbidden-key list also exists in
  **three drifting copies** (`check-conformance.sh:24`, `validate-critique.sh:15`, schema `$comment`).
  **Fix:** make the *schema itself* enforce seat-blindness (close `per_criterion`); single-source the
  forbidden list; treat jq and ajv as must-agree (or generate the jq checks from the schema).

- **M3 — Multimodal judging is framed vision-only.** Invariant 8 ("design_quality/originality cannot be
  scored from DOM alone") is correct but one-sided: for web UI, withholding **code** hurts a judge
  *more* than withholding screenshots, and VLMs are weakest on exactly the "craft" axis (WebDevJudge,
  https://arxiv.org/abs/2510.18560 — "Withholding code leads to a significantly larger performance drop
  than withholding screenshots"; best judge 70% vs 84% human — also a B2 validity data point). The
  `rubric.md` few-shot anchors are **unfilled placeholders** — anchored per-dimension scoring is the
  single highest-value reliability lever for VLM judging (WebVR, https://arxiv.org/abs/2603.13391
  [2026 preprint, directional] — structured rubric lifted alignment ~59–67% → ~77–87%).
  **Fix:** require screenshot **and** code/DOM in the judging context; fill the anchors; optionally
  backstop "craft" with element-level metrics.

- **M4 — Feedback threading degrades output, and the iteration ceiling is high.** `WORKFLOW.md:99` (L2)
  says the generator "carries full history + prior critique on iteration." Appending the transcript
  both hurts quality and lengthens context (which *worsens* B1's hacking — length is Pan et al.'s
  secondary driver). Most gain arrives in ~3 cycles, against the 5–15 / ceiling-20 budget (In-Place
  Feedback, https://arxiv.org/abs/2510.00777; *Another Turn, Better Output?*,
  https://arxiv.org/abs/2509.06770 — "vague feedback often plateaus or reverses," "size expansion with
  minimal conceptual change"). **Fix:** re-anchor feedback on the *current* artifact rather than
  accumulating; add a markup/CSS bloat guard across rounds; justify the ceiling against diminishing
  returns; re-examine the "middle iteration often preferred" prior for code/design (gains tend to come
  early).

- **M5 — Tooling framing is stale.** `WORKFLOW.md:202` (L10) calls Playwright MCP a "Going further" /
  community-wired pattern; it is now **first-party Microsoft**, versioned (v0.0.76, 2026-06-10), with a
  `--caps=devtools` capability (https://github.com/microsoft/playwright-mcp). **Chrome DevTools MCP**
  (official, v1.4.0, 2026-06-23, https://github.com/ChromeDevTools/chrome-devtools-mcp) is named in the
  companion stack but never wired — so nothing occupies a performance/Core-Web-Vitals axis.
  **Fix:** reclassify Playwright as official + pin a version; either wire Chrome DevTools MCP or drop
  performance from the stack (it isn't a rubric criterion — the *inconsistency* is the defect).

### MINORS — quick, high-confidence

- **Front-2 salvage:** the **Y-statement / MADR** are sourceable at `adr.github.io` (it cites the
  Y-statement from Zdun et al. and references MADR) — they were rejected only for being pinned to the
  wrong URL (martinfowler.com). **Reinstate with the corrected citation** instead of leaving "(unverified)".
- **WCAG date drift:** `RESEARCH-LOG.md:283` says "5 Oct 2023"; W3C now shows an **edited Recommendation
  dated 12 December 2024** (status/contrast unaffected). Update the date.
- **axe-core staleness:** the conformance fixture (`check-conformance.sh:31`) and examples reference
  `4.10.0`; current is **4.12.1** (the ~57% coverage figure is version-independent, so the G4 claim
  itself still holds).
- **DTCG `$type` wording (`RESEARCH-LOG.md:85`):** "a token is valid with `$value` alone" is incomplete
  — a token's type must be **resolvable** (explicit, inherited from the nearest parent group's `$type`,
  or via reference) or the token is **invalid** (DTCG draft format §). Tighten before anyone builds the
  conformance bridge. Note there is **no official DTCG JSON Schema** yet — build the (unbuilt) bridge
  against **Style Dictionary v5** (parses 2025.10 incl. OKLCH) or Terrazzo, not hand-rolled.
- **`rubric.json` slop_flags:** `"verified": true` (lines 31-37) sits beside penalty numbers (0.4/0.2)
  while the file header says all numbers are unverified. `verified` means "this is a real SKILL.md
  pattern," not "this penalty value is verified." Disambiguate (e.g., `pattern_verified` vs the penalty
  staying unverified).
- **Citation hygiene (matches the doc's own standard):** the "~24% Claude order-consistency" and
  "~95%/~90% pairwise/pointwise" figures (`RESEARCH-LOG.md` G8) trace only to a Medium post — re-source
  to MT-Bench (which reports GPT-4 ~65%, a different model/setting) or drop. Same for any "<20% VLM font
  accuracy" / vendor "billions of screens" figures if they appear downstream.
- **Blocklist drift in the human bridge:** `human-seat-to-json.sh:13` deletes 11 keys, but
  `validate-critique.sh:15` bans 14 — a human form carrying `self_preference`/`generator_model_family`/
  `method` would pass the stripper then fail validation. Align the two lists.
- **Style Dictionary is v5** (not v4 as in `RESEARCH-LOG.md:89`); **Figma native DTCG import/export** is
  slated ~Nov 2026 (today via plugins/REST) — nice-to-have, not load-bearing.

---

## 2. Front-by-front detail

### 2.1 Front 1 — Source re-verification (all VERIFIED claims HOLD; fetched 2026-06-28)

No dead/blocked links. No VERIFIED claim with an unsupported source. Staleness flags are the only deltas.

| Claim (as carried) | Source re-fetched | Verdict |
|---|---|---|
| Single-track generator→evaluator, NOT a bake-off | anthropic.com/engineering/harness-design-long-running-apps — "a multi-agent structure with a generator and evaluator agent" + "5 to 15 iterations per generation" | **HOLDS** |
| 5–15 iterations | same — "I ran 5 to 15 iterations per generation…" | **HOLDS** |
| Playwright MCP is the evaluator's tool | same — "I gave the evaluator the Playwright MCP, which let it interact with the live page directly before scoring each criterion" | **HOLDS** |
| Four criteria + verbatim defs | same — all four quoted verbatim (design quality / originality / craft "competence check" / functionality) | **HOLDS** |
| Weight DIRECTION design+originality > craft+functionality | same — "I emphasized design quality and originality over craft and functionality. Claude already scored well on craft and functionality by default" | **HOLDS** |
| Per-criterion hard-threshold gate = CODING harness only | same — the "hard threshold… the sprint failed" sentence is in the full-stack **coding** section; the frontend section uses scoring + refine/pivot. Log's "deliberate unverified transfer to design" framing is correct | **HOLDS** |
| Agents over-grade own work; middle iteration often preferred | same — both quoted verbatim | **HOLDS** |
| "Spend boldness in one place" | **SKILL.md** (not the harness post) — log attributes it to SKILL.md, which is correct | **HOLDS (as attributed)** |
| SKILL.md: 3 slop clusters, 3 behavioral tells, token vocab (4–6 hex / multi-role type / signature) | raw.githubusercontent SKILL.md — all verbatim | **HOLDS** |
| "Banned-font list" + "shadows at 0.1 opacity" ABSENT from current SKILL.md | same — not present (practitioner lore) | **HOLDS** |
| Playwright `--caps=vision` text; default = a11y snapshots; screenshots persist without vision | playwright.dev/mcp/capabilities + /vision-mode — "Coordinate-based mouse tools…Requires a vision-capable LLM"; "By default…uses accessibility snapshots"; `browser_take_screenshot` is a core tool | **HOLDS** |
| WCAG 2.2 AA current W3C Rec; 4.5:1 / 3:1 | w3.org/TR/WCAG22 — "W3C Recommendation 12 December 2024"; SC 1.4.3 quotes | **HOLDS — date in log is stale (says 2023-10-05)** |
| DTCG 2025.10; `$value` required, `$type` optional; OKLCH; no newer version | designtokens.org/tr/2025.10 — quotes confirmed; OKLCH in colorSpace list; drafts still labeled 2025.10 | **HOLDS** |
| Deque "57.38% of total issues…automated" / ~43% manual | deque.com/automated-accessibility-coverage-report — verbatim (13,000+ pages / ~300k issues) | **HOLDS** |
| axe-core #4415 "57% of WCAG issues automatically" | github.com/dequelabs/axe-core/issues/4415 — verbatim, issue **Open** | **HOLDS** |
| Tailwind v4 `@theme` exists | tailwindcss.com/docs/theme | **HOLDS (note: log doesn't actually assert it)** |
| axe-core version | github releases / npm — latest **4.12.1** (~2026-06-12); log pins no version | **HOLDS; fixtures' `4.10.0` is stale** |

### 2.2 Front 2 — Rejected-claims audit: SOUND
All 33 rejections are correct (source-mismatch / overstated specific / fabricated / unverifiable). The
"true-but-mis-cited" ones are handled correctly (re-cited or flagged "real elsewhere"), so **no real
fact is lost**. Load-bearing rejections re-confirmed against primary sources:
- **N≈4 saturation** — cited arxiv 2507.08944 is about parallel multi-agent *speedup*, not best-of-N
  saturation. Correctly rejected; no fixed N≈4 constant exists (it's model-dependent).
- **≈3-critic / 20–30-idea plateaus** — neither number is in arxiv 2602.20408. Correctly rejected.
- **`min(16, cpu_cores−2)`** — not in Claude Code docs; the docs cite "5 to 30" worktree subagents and
  there are open feature requests for a configurable cap → actively contradicted. Correctly rejected.
- **SKILL "tone taxonomy" / four-question framework** — not in live SKILL.md. Correctly rejected (this
  was the load-bearing diversity lever).
- **"Fresh context per iteration" / "files-not-context is the central principle"** — the article's
  actual stated principle is "find the simplest solution possible…"; context resets were a Sonnet-4.5-era
  feature **removed** in the Opus-4.6 harness. Correctly rejected (the broader file-state idea is real,
  just not THIS article's framing).
- **Nygard 5-element / MADR / Y-statement** — correctly rejected at the cited URLs; **but Y-statement
  and MADR are sourceable at adr.github.io** → see the Minor salvage above.

### 2.3 Front 3 — Contract scrutiny (conformance output + adversarial probes)

**`scripts/check-conformance.sh` (local, jq-fallback path because ajv absent):**
```
PASS  C1 schema is seat-blind (closed objects, no seat-correlated keys)
PASS  C2 auto-emitted and human-emitted critique-<k>.json are byte-identical
PASS  C3 both critiques validate against the schema (jq fallback; install ajv for full draft-2020-12)
PASS  C4 loop reads ONLY NEXT_FINDINGS.json as the baton (no sidecar/.md/FINDINGS.md)
PASS  C5 viewports pinned to 1440/768/375 in capture + schema
PASS  C6 rubric encodes verified DIRECTION; numbers labeled unverified
ALL CONFORMANCE CHECKS PASSED
```
`shellcheck -S error *.sh` → clean.

**Adversarial seat-blindness / validator-parity probes** (built valid base = the conformance `$GATED`
payload, mutated with `jq`, run through `validate-critique.sh`). ajv was not installed offline; schema
verdicts below are by JSON-Schema semantics + the confirmed structural fact that `gate.per_criterion`
is `{"type":"object"}` (open):

| Probe | jq validator | Real schema (ajv) | Meaning |
|---|---|---|---|
| base (control) | ACCEPTED | valid | — |
| **adv1**: seat watermark in `scores.craft.rationale` free text | **ACCEPTED** | **valid** | byte-identity/seat-blindness defeated via free text (validators scan key *paths*, not *values*) |
| **adv2**: novel key in open `gate.per_criterion` | **ACCEPTED** | **valid** | open object is a seat channel |
| adv2b: literal `seat` key in `gate.per_criterion` | REJECTED (grep) | **valid** | jq grep catches the *listed name*; ajv would accept → C1 "unrepresentable" is false |
| adv3: unknown top-level key | ACCEPTED | **invalid** | jq doesn't enforce `additionalProperties:false` |
| adv4: duplicate viewports `[1440,1440,768]` | REJECTED | **valid** | jq stricter; schema enum+minItems3 allows repeats |
| adv5: `recommendation:"banana"` | ACCEPTED | **invalid** | jq doesn't check the enum |
| adv6: `weighted_total:"lots"` | ACCEPTED | **invalid** | jq doesn't check the type |

**Per-check assessment:**
- **C1** greps the *schema text* for declared forbidden keys — it does not (and cannot) prevent a
  *document* from carrying seat signals in the open `per_criterion` object or in free text. "Unrepresentable" overstated.
- **C2** is tautological (same fixture both paths; see B1). It proves jq determinism, not seat-equivalence.
- **C3** runs the jq fallback here, which disagrees with ajv in both directions (M2).
- **C4** verifies the generator block doesn't reference 3 forbidden filenames — but the generator
  demonstrably also reads DESIGN.md, BRIEF.yaml, tokens/, and the non-existent `SCORES.md`. "Reads ONLY
  NEXT_FINDINGS.json" is inaccurate; the true invariant is "the single *feedback baton* is NEXT_FINDINGS.json."
- **C5** is sound: the shared pinned capture (`run-harness.sh:49-52`, before the evaluator) means both
  seats consume identical pixels within a run. (Cross-run byte-stability still needs the pinned
  Chromium noted in preconditions; heights 900/1024/812 are labeled unverified.)
- **C6** is sound: it genuinely proves `rubric.json` encodes the direction and flags the numbers unverified.

### 2.4 Front 4 — Completeness / 2026 practices
Full blocker/major/minor list folded into §1 (B3, M1–M5) and the Minors. Recency note: several
supporting cites are 2026 arXiv preprints (single-fetch, directional) — load-bearing weight rests on the
peer-reviewed anchors (ICLR/NeurIPS/ACL: Pan; null-model; JudgeBench; Panickssery; Verga PoLL; MT-Bench;
DeepMind self-correct; CriticGPT; Length-Controlled AlpacaEval). Items confirmed **current / correct**
(do not "fix"): DTCG 2025.10; the ~57% axe figure; the perceptual-novelty "unverified" flag.

### 2.5 Front 5 — Open-risk reassessment
| Stated risk (HARNESS §16 / README) | Reassessment |
|---|---|
| 1. κ across the two distributions (byte-identity ≠ score-equivalence) | **UNDERSTATED.** Post-probe it's worse: real seats aren't even byte-identical (B1). The README line "byte-identity…is proven" is the misleading claim. Underpins B1. |
| 2. Grid quantization may cost ranking resolution | Correctly a risk — but the **cost/benefit is now inverted**: you pay resolution to buy a byte-identity that won't materialize. Reconsider quantizing the auto EV at all. |
| 3. Vision-channel prompt-injection residual | Correctly scoped; **give credit** for the deterministic gate recomputation (bounds the blast radius to non-gating aesthetic scores). Sits alongside the larger undocumented gameability class (B3). |
| 4. Human pairwise non-transitivity (L8) | Slightly **OVERSTATED** — only bites the *optional* fan-out (L3/L8); the single-track default has no pool to aggregate. |
| 5. design.md alpha pin (same-SHA drift) | Correctly scoped, **minor**; arguably over-prominent for a same-SHA edge case. |
| 6. Validator parity (jq ≠ draft-2020-12) | **UNDERSTATED** → M2 (the validators actively disagree; seat-blindness lives only in the jq grep). |
| **Add to §16** | reward-hacking/eval-gaming; judge validity; self-preference/family bias; length bias; feedback-accumulation degradation. |

---

## 3. The simpler-structure recommendation (the harness's own cited principle)
The Anthropic post's stated principle is *"find the simplest solution possible, and only increase
complexity when needed."* By that test, the **byte-identity contract — and the sidecar +
EV-quantization + triple forbidden-list machinery built to serve it — optimizes for a property that is
both unattainable (free text) and unnecessary.** The attainable, more meaningful contract is **semantic
interchangeability**: one shared gated schema (already built) + a measured score-tolerance / κ band on
the calibration gold set (slot already exists, empty). Pivoting to that:
- removes the staged C2 check, the EV-quantization ranking cost, and the seat-blindness-via-grep fragility;
- replaces "proven" with something you can actually measure;
- and turns the chief open risk (κ) from a footnote into the headline metric, where it belongs.

This is the highest-leverage single change and it *reduces* the harness's surface area.

---

## 4. What's already right — do not relitigate
- Pairwise-with-swap for position bias (MT-Bench) — current and correct (fixes *position* only).
- Separate evaluator / "generator never judges itself" — validated (DeepMind 2310.01798: LLMs struggle
  to self-correct without external feedback; self-refine amplifies self-bias).
- Vision-grounded judging invariant — aligned with 2026 frontend SOTA (needs the image+code expansion, M3).
- axe-floor-is-PARTIAL and perceptual-novelty-unverified flags — both correct.
- CRDAL "not replicated for frontend, unverified" caveat — accurate.
- The entire VERIFIED / (unverified) discipline in RESEARCH-LOG — keep it; it's the doc's strongest asset.

---

## Appendix A — Proposed paste-ready text (SUGGESTIONS for the author; nothing here is applied)

### A1 — Re-word the swappable-seat contract (replaces the "proven byte-identity" framing)
> **Swappable seat (structural, not proven-equivalent).** Both seats emit the *same gated schema*; a
> shared wrapper strips a seat-key blocklist and canonicalizes via `jq`, so the loop reads a normalized
> artifact. This is **structural alignment + normalization, not a proof of indistinguishability**:
> free-text fields and the open `gate.per_criterion` object can still carry seat-correlated signal, and
> two independent judges will not produce byte-identical output in practice. **Real-seat byte-identity
> and cross-seat score-equivalence (κ) are UNVALIDATED and must be measured on the calibration gold
> set.** `check-conformance.sh` proves the schema is *closed on its named objects* (C1), that the
> wrapper canonicalization is *deterministic on identical input* (C2 — note: a staged fixture, not two
> live seats), and that the loop's *feedback baton* is `NEXT_FINDINGS.json` (C4).

### A2 — New §16 entries (risks to add)
> 7. **Reward hacking / optimizing against the judge.** The loop refines the generator against the
>    evaluator and selects on the evaluator's score; an imperfect proxy can have its ratings rise while
>    true quality stalls or drops (Pan et al. 2024). Mitigations in place: fresh-context evaluator
>    (kills the shared-context driver). Mitigations still owed: make the selection/stop signal partly
>    independent (cross-family judge and/or human spot-check of the selected artifact); bound generator
>    context to limit the length-driven variant.
> 8. **Judge validity (not just reliability).** §17 proves stability (κ/byte-identity), not correctness.
>    A judge can be swap-consistent and systematically wrong (JudgeBench, ICLR'25). Add periodic
>    human-vs-judge agreement on a held-out gold set (`calibration/agreement.json`) as a validity gate.
> 9. **Self-preference / same-family bias.** Generator and evaluator are likely the same family; self-
>    preference tracks self-recognition and familiarity. Default to a cross-family evaluator; make the
>    k=3 panel cross-family.
> 10. **Length/verbosity bias.** Position-swap does not neutralize it. Add a length-controlled clause.
> 11. **Feedback-accumulation degradation.** Carrying the full critique transcript degrades output and
>     lengthens context (worsening #7). Re-anchor feedback on the current artifact; guard markup bloat.

### A3 — Conformance-claim re-scoping (README + §17)
- README:40 — change "ALL CONFORMANCE CHECKS PASSED (6/6)" to add: *"(these prove schema closure,
  canonicalization determinism on a staged payload, baton path, viewport pin, and rubric direction —
  NOT real-seat byte-identity or score-equivalence)."*
- §17 C2 — relabel from "SWAPPABLE SEAT / byte-identity" to "wrapper canonicalization determinism
  (staged)," and note that the two paths share one input by construction.

### A4 — Scaffold fixes (B2)
- Add `.claude/agents/generator.md` and `.claude/agents/supervisor.md`, or remove the `--agent generator`
  / `agents/supervisor.md` references and mark them TODO in README's preconditions.
- In `run-harness.sh`, either write a `SCORES.md` trend file or change the generator prompt (`:44,:48`)
  to read `scores.csv`.
- `rubric.json:6` → `"axe_core_version": "4.12.1"`; update the `check-conformance.sh:31` fixture to match.

---

## Appendix B — Reproduce the probes
```sh
DC=<path>/design-competition
PROJECT="$DC" bash "$DC/check-conformance.sh"           # baseline 6/6
T=$(mktemp -d); cp "$DC"/... ; # base = the $GATED block in check-conformance.sh:29-45
jq '.scores.craft.rationale += " [emitted by AUTO seat; EV=4.12]"' base.json > adv1.json
jq '.gate.per_criterion = {"x_seatchan":7}'                 base.json > adv2.json
jq '. + {"x_extra_toplevel":1}'                             base.json > adv3.json
jq '.recommendation="banana"'                               base.json > adv5.json
for d in base adv1 adv2 adv3 adv5; do bash "$DC/validate-critique.sh" "$T/$d.json"; done
# adv1, adv2, adv3, adv5 all print "ok:" under the jq fallback.
```

---

## Appendix C — Source-quality flags (do not ship as fact)
- Re-source or drop the Medium-only "~24%" and "~95%/~90%" judge figures (RESEARCH-LOG G8).
- Treat 2026 preprints (WebVR, WebDevJudge follow-ons, Vision2Web, In-Place Feedback, Vision-Guided
  Refinement, Berkeley test-retest) as directional; anchor on the peer-reviewed cites in §1.
- WCAG date → 2024-12-12; axe-core → 4.12.1; Style Dictionary → v5; DTCG `$type` → "must be resolvable."

*End of review — read-only; no harness files, tags, or git state were modified.*
