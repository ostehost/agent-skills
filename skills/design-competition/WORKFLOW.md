# Design Competition Workflow — Canonical Layered Spec

> An agentic loop that **generates a frontend design, scores it against an explicit rubric, feeds
> critique back, and iterates until it converges.** It runs in two interchangeable modes — **Human**
> (a person judges) and **Playwright/Auto** (an AI evaluator judges a live page) — over the *same*
> substrate, loop, rubric, and critique schema. **Only the evaluator seat swaps.**

**Status:** foundation + all 10 gaps **resolved** against adversarially-verified sources. Each gap
below carries a one-line verdict + grade; full citations, exact quotes, recommended schemas, and the
list of *rejected* claims live in [`RESEARCH-LOG.md`](./RESEARCH-LOG.md). Anything not confirmed by a
primary source is marked **(unverified)** — do not promote those to fact.

---

## ⚠️ Terminology & scope correction (read first) — [G9, mixed]

The research forced two corrections to the naming and shape of this spec:

1. **"Design competition" is a drifted, non-standard term.** It does not appear in Anthropic's
   engineering writeup or the official `frontend-design` plugin. Use precise terms instead:
   - **Generator–evaluator (GAN-style) harness** — one design refined over iterations against a
     rubric. **This is Anthropic's actual *published* approach.**
   - **Best-of-N candidate selection** (with a **pairwise LLM-as-judge** or human) — N designs
     generated in parallel, then ranked and a winner picked.
   - Reserve *"design competition"* as a plain-English label, mapped explicitly to one of the above.
2. **Anthropic's published loop is single-track, not a parallel bake-off.** It runs **one** generator
   + **one** evaluator over **5–15 sequential iterations**. The parallel "N competing candidates"
   idea (Layer L3 below) is a **community composition layered *in front of* that loop**, not part of
   Anthropic's design harness. Decide which you actually want: deep single-track refinement, fan-out
   best-of-N, or fan-out-then-deep-iterate-the-winner (the recommended hybrid).

Both modes (Human / Playwright) and the swappable-seat model are **verified-solid** (G4, G10). The
*competition* framing is the part to treat as an optional, community-built outer layer.

---

## The core principle: the evaluator is the only swappable layer

```
                          ┌─────────────────────────────────────┐
   shared substrate  ─────│ L0 Tokens / DESIGN.md (one swap = one direction)
                          ├─────────────────────────────────────┤
   OPTIONAL outer    ─────│ L3 Best-of-N fan-out (community layer, not Anthropic)
                          ├─────────────────────────────────────┤
   CORE loop         ─────│ L1 Brief → L2 Generate                │
   (GAN-style        │    │            ↑                  │       │
    harness)         │    │            │            ┌─────▼─────┐ │
   PLUGGABLE SEAT    ─────│            │            │ L4 EVALUATE│◄── Human | Playwright | Hybrid
                          │            │            └─────┬─────┘ │
   shared language   ─────│      L6 Critique ◄── L5 Rubric (same criteria both modes)
                          │            │                          │
   shared control    ─────│      L7 Iterate (refine|pivot) → L8 Converge / Select
                          └─────────────────────────────────────┘
```

Everything except **L4 (who judges)** and the **binding** that captures their verdict is identical
across modes — that is what makes a run reproducible whether a human or Playwright sits in the seat,
and what lets you start Human and finish Auto on the same artifacts. **Verified solid (G4).**

---

## Layer reference

### L0 — Substrate: design tokens + `DESIGN.md`  *(shared)* — [G1, solid]
Split the design contract into **two files with different audiences**, both at **project root**,
cross-referenced from `CLAUDE.md` / `AGENTS.md`:
- **`DESIGN.md`** — the *why* + semantic rules (prose, agent-readable). Recommended ~9–10 sections:
  Overview/atmosphere · Color palette & roles · Typography rules · Layout principles · Depth &
  elevation · Component stylings (with states) · **Signature** (the one element the page is
  remembered by) · Do's & Don'ts · Responsive behavior · Agent prompt guide.
- **A tokens file** — the *what* (exact values). Pick one: **W3C DTCG JSON** (interop with
  Figma/Style Dictionary; a token needs `$value`, `$type` is *optional*), a Markdown-table token file
  (`designtoken.md`, LLM-native), or **CSS custom properties** (Wiegold's "swap the token file and
  re-run").
- **Machine-readable = exact values not adjectives** (`#855300`, not "warm brown"), deterministic
  structure an evaluator can diff, and **primitive→semantic layering** so competing variants vary the
  *semantic* mappings while sharing the *primitive* scale (keeps them comparable).
- *Provenance:* `DESIGN.md` originates with Google Stitch; Anthropic's `frontend-design` SKILL
  prescribes the token *vocabulary* (4–6 named hex, multi-role type, signature) but does **not**
  mandate a `DESIGN.md` file. → [details + DTCG example](./RESEARCH-LOG.md#g1)

### L1 — Brief / Intent  *(shared)* — [G2, mixed]
**Two layers.** No formally validated schema exists — the field set is synthesized **(unverified as a
standard)** but the substance is sourced.
- **Layer 1 — Intent (required):** `subject` (one concrete product, not a category), `audience`,
  `job` (the page's single job), `tone` (one-sentence visual thesis).
- **Layer 2 — Aesthetic direction = a compact token system, produced *before* code:** `color` (4–6
  named hex), `type` (2+ roles: characterful display used with restraint, body, utility/data),
  `layout` (one sentence + ASCII wireframe), `motion` (2–3 intentional motions, philosophy not
  effects), `signature`, `references` (evocative, non-prescriptive), **`avoid`** (negative list).
- **The `avoid` list defeats slop:** never Inter/Roboto/Open Sans/Lato/system fonts; no purple
  gradients on white; no generic SaaS card grid (OpenAI source); and the three SKILL default clusters
  that are *themselves* now slop (cream+serif+terracotta · near-black+acid-green · broadsheet/hairline).
- **Mandatory self-critique pass** before writing code: confirm the plan is specific to *this* brief,
  not a recycled default. → [drop-in YAML brief](./RESEARCH-LOG.md#g2)

### L2 — Generator  *(shared)*
Produces a candidate (HTML/CSS/JS bound to L0 tokens) from L1 + L0. **Never judges its own work**
(self-eval bias → models praise mediocre output). **Anchors on the *current* artifact + the latest
critique baton, not an accumulated transcript** (M4: appending full history degrades output, lengthens
context, and worsens reward-hacking; most gain arrives in ~3 cycles). Carries a markup/CSS bloat guard
across rounds. Use the official **`frontend-design` plugin** as the generation surface (G10).

### L3 — Best-of-N fan-out  *(OPTIONAL outer layer — community, not Anthropic)* — [G3, mixed]
Generate **N competing candidates**, screen them, keep one, *then* hand the winner to the core L2/L4
loop. Don't conflate fan-out budget with deep-iteration budget.
- **N = 3 default (up to 5)** — this is the **tool default** (Stitch `variants()`, parallel-worktrees),
  **not a benchmarked optimum**. The "quality saturates at N≈4" claim **failed verification
  (unverified)**. The real ceiling is *review bandwidth*: ~5–10 parallel before the merge/review step
  becomes the bottleneck.
- **Enforce diversity deliberately** — independent samples converge on their own. Assign each
  candidate a distinct direction + persona + seed (not temperature alone). Stitch: `creativeRange:
  "REIMAGINE"` + target `aspects`. *Caveat:* the SKILL preaches depth-over-breadth, so use fan-out to
  pick a **direction**, then switch to single-track depth.
- **Present side-by-side** as a Playwright screenshot grid you assemble yourself (`page.screenshot()`
  per candidate → tile into one HTML page). Judge: human pick · cheap AI score-from-screenshots ·
  thorough AI drives each live candidate (×N cost).
- **Mechanisms:** git worktrees (full-app, isolated trees/branches, **~15× tokens**, ~5–10/dev before
  merge bottleneck) · parallel subagents (component-level, **no nesting**) · Stitch `.variants()`
  (screen-level, 1–5/call). The `min(16, cpu_cores−2)` concurrency formula is **(unverified)**.
  → [mechanism tradeoff table](./RESEARCH-LOG.md#g3)

### L4 — Evaluator  *(THE SWAPPABLE SEAT)* — [G4, solid]
Both seats consume the **same inputs** (a running build at a local URL + the design spec) and emit the
**same output shape** (per-criterion critique + verdict + prioritized findings) → drop-in interchangeable.

| | **Human mode** | **Playwright / Auto mode** |
|---|---|---|
| Who judges | person | **fresh-context evaluator subagent, no Write/Edit tools** |
| Sees | live render, side-by-side | live page via **Playwright MCP** (navigate/click/inspect DOM/screenshot) |
| Order | **"Live Environment First"** (interact before static analysis) | live interaction **before** screenshot capture |
| Protocol | design-review: **8 phases** (Prep→Content/Console), viewports **1440/768/375**, contrast **≥4.5:1** | 4-criterion rubric, few-shot calibrated |
| Output | triaged findings: `Blocker / High / Medium / Nitpick` | same critique artifact |

Pin a **fixed viewport set (1440/768/375)** for *both* seats so scores are comparable. Keep the
evaluator **write-locked & fresh-context** in both modes (the human reviews, never edits).
→ [evaluator + design-review protocol](./RESEARCH-LOG.md#g4)

### L5 — Rubric / Criteria  *(shared language — the most important shared layer)* — [G5, solid]
**Four criteria (verbatim, verified):** **Design quality** (coherent whole vs collection of parts) ·
**Originality** (custom decisions vs template/library/AI defaults) · **Craft** (typography, spacing,
color harmony, contrast) · **Functionality** (usability/task completion).
- **Verified weighting *direction*: design quality + originality weighted *over* craft +
  functionality** (Claude already scores well on the latter by default).
- **(unverified, recommended impl):** exact weights `0.35 / 0.35 / 0.20 / 0.10`, a 0–10 scale, JSON
  output schema, gating rules, and verdict thresholds — Anthropic publishes the *direction*, not the
  numbers. Label them as choices, not facts.
- **AI-slop checklist (verified from SKILL.md):** the three default look-clusters above + behavioral
  tells (scattered motion, gratuitous `01/02/03` markers, templated copy). The banned-font list and
  "shadows at 0.1 opacity" are **practitioner lore**, absent from current SKILL.md — pin & re-verify
  your SKILL version.
- **Few-shot calibration: method verified** (seed the evaluator with examples + detailed score
  breakdowns → reduces drift & leniency); **example numbers are (unverified)**. → [rubric + checklist](./RESEARCH-LOG.md#g5)

### L6 — Critique artifact  *(shared schema)* — [G6, solid]
One record both seats produce identically. **Anthropic publishes no literal JSON schema — the record
below is synthesized** from its prose rubric + the LLM-as-judge convention.
- **Full form (JSON):** `candidate_id`, `round`, `evaluator{type:human|ai}`, `verdict`
  (`PASS`/`NEEDS_WORK`), `scores.<criterion>{score,rationale}`, `quality_floor{}` (responsive,
  keyboard focus, reduced-motion — any false ⇒ NEEDS_WORK), `change_requests[]`
  (`{criterion,expected,observed,evidence,severity,fix}`), `recommendation`
  (`refine`/`pivot`/`accept`), `recommendation_rationale`, `confidence`.
- **Gate per-criterion, not on the average.** Every finding is **evidence-bound** (screenshot / diff /
  code location). The numeric scale and `confidence` field are **(unverified)** add-ons.
- **Minimal form (matches Anthropic's shipped harness):** bare verdict on line 1 + bulleted findings
  list that *becomes the next builder session's prompt*. → [full field reference](./RESEARCH-LOG.md#g6)

### L7 — Iteration control  *(shared)* — [G7, solid]
**Do not stop on "score reached threshold"** — real evaluators plateau *with headroom remaining* and
scores are **non-monotonic**.
- **Bounded loop:** hard iteration cap (**8–15 for design, 20 absolute ceiling**; Anthropic ran 5–15)
  + budget cap (tokens/$/wall-clock — mandatory for unattended runs) + plateau/no-progress early-exit
  (best score flat ≥2–3 rounds — *heuristic, unverified*) + per-criterion regression gate (any
  criterion below its floor fails the round).
- **Selection rule:** **keep every iteration's artifact and pick the best across all of them — never
  assume the last iteration wins.**
- **Anti-fixation:** refine-vs-pivot decision each round (the primary lever) · tried-it memory /
  forced novelty · up-front aesthetic commitment · **metacognitive co-regulation supervisor (CRDAL)**
  for high-value runs (escaping local optima came from *better feedback, not more iterations* — but
  the study is battery-pack design, **not yet replicated for frontend, unverified**).
- **Human mode:** stop = explicit human ship; still wrap in a budget/iteration ceiling. → [stop conditions](./RESEARCH-LOG.md#g7)

### L8 — Convergence / Selection  *(shared)* — [G8, mixed]
- **Model A — iterative converge** (Anthropic's published approach): single design, 5–15 iters,
  refine/pivot, **don't blindly take the last iteration**.
- **Model B — best-of-N selection:** **single-output rubric scoring to screen** all N (cheap), then
  **pairwise/arena judging to break ties**. *(The "~95% pairwise vs ~90% single-output" and "~24% Claude
  order-consistency" figures trace only to a Medium post and are **(unverified)** — MT-Bench reports a
  different ~65% GPT-4 order-consistency in a different setting; treat the direction, not the numbers.)*
  **Mitigate position bias** — swap A/B order and run both. Tournament needs N−1 comparisons (math property).
- **Synthesis/grafting (optional, risky):** graft self-contained elements from runners-up, then
  **re-score** for coherence (grafting risks the "collection of parts" failure). Not an established
  named pattern — **(unverified)**.
- **Record the decision as an ADR** (short markdown: winner + artifact link, per-dimension scores for
  winner & runners-up, selection method + judge model + calibration set, grafted elements, human
  override + why, date/status). → [selection + ADR fields](./RESEARCH-LOG.md#g8)

### L10 — Mode bindings  *(the only mode-specific wiring)* — [G10, solid]
One generation surface (`frontend-design` plugin); swap the judge behind a **mode flag**; both write
to a **shared feedback file the generator reads next pass**.
- **Mode A (Auto/Playwright):** evaluator at `agents/evaluator.md` (no Write/Edit), invoked headless
  (`claude --agent evaluator -p "…"` → `PASS`/`NEEDS_WORK` + findings). **Playwright MCP is now a
  first-party Microsoft tool** (`microsoft/playwright-mcp`, versioned — pin it; `--caps=vision` /
  `--caps=devtools`), so wiring it is configuration, not a custom build — though it was still not
  *shipped inside* `cwc-long-running-agents` (M5). Loop = bash `while` alternating generator/evaluator,
  writing the gated critique to the `NEXT_FINDINGS.json` baton; gating via a `PreToolUse` read-gate +
  control hooks (`kill-switch.sh`, `steer.sh`, `commit-on-stop.sh`).
- **Mode B (Human):** per-worktree dev servers + `git diff main`; merge the winner + cleanup. Capture
  critique in a REVIEW-SHEET that `human-seat-to-json.sh` converts to the **same gated artifact** the AI
  evaluator emits — keeping modes structurally interchangeable (not proven-equivalent; see L4/HARNESS §16).
- **Companion stack (community):** TypeScript LSP · Frontend Design · Playwright (first-party) ·
  GitHub · Vercel. **Chrome DevTools MCP** (official, `ChromeDevTools/chrome-devtools-mcp`) is *optional
  and NOT wired* here — performance/Core-Web-Vitals is not a rubric criterion, so it stays out of the
  loop rather than being half-integrated (M5). → [wiring tables](./RESEARCH-LOG.md#g10)

---

## Shared vocabulary (use these exact terms in both modes)

| Term | Meaning |
|---|---|
| **harness** | the whole scaffold around the model (Anthropic's term) |
| **generator–evaluator (GAN-style) harness** | the core single-track build→critique→iterate loop |
| **best-of-N candidate selection** | the optional parallel fan-out + winner-pick (L3/L8 Model B) |
| **substrate / tokens** | L0 — the swap-cheap design-system layer |
| **brief / intent** | L1 — aesthetic direction, not pixels |
| **generator** | L2 — makes candidates; never judges itself |
| **candidate / variant** | one design entry |
| **evaluator / seat** | L4 — whoever judges (human \| Playwright \| hybrid) |
| **rubric / criteria** | L5 — the four scoring dimensions + weight direction |
| **critique** | L6 — per-criterion score + evidence-bound change requests + refine/pivot |
| **LLM-as-judge (pointwise / pairwise)** | the scoring component (screen / tie-break) |
| **baton** | the feedback file (`NEXT_FINDINGS.md` / `FINDINGS.md`) that keeps the loop alive |
| **refine vs pivot** | L7 — improve current direction vs switch aesthetic |
| **convergence** | L8 — winner locked |

> Avoid: "design competition" as a precise term; "GAN harness" implying adversarial *training* (it's
> only role-separation, no gradients); "LLM-as-judge" for the *whole* loop (it's only the scoring part).

---

## What the research could NOT verify (carry as risk, don't ship as fact)
The verifier rejected **33 claims**; the load-bearing ones for this spec:
- Exact rubric weights / score scale / JSON schema / few-shot example numbers — **none published by Anthropic** [G5,G6].
- N≈4 quality-saturation and the "≈3 critics / 20–30 idea" diversity plateaus — **source mismatch** [G3].
- `min(16, cpu_cores−2)` concurrency cap — **unconfirmed** [G3].
- A SKILL "tone taxonomy" / four-question diversity framework — **fabricated; not in SKILL.md** [G3].
- "Each iteration starts with fresh context" / "files-not-context is the central principle" — **overstated** [G7].
- ADR five-element format / MADR / Y-statement attributed to the cited pages — **source mismatch** (real elsewhere) [G8].

Full rejected-claims list with reasons: [`RESEARCH-LOG.md#rejected-claims`](./RESEARCH-LOG.md#rejected-claims).
