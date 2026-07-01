# Research Log — Design Competition Workflow

Citation-backed, **adversarially-verified** findings that fill the `🔬 RESEARCH GAP` markers in
[`WORKFLOW.md`](./WORKFLOW.md). Produced by the `design-competition-research` workflow
(10 gaps → research → skeptic verification → synthesis; 20 agents). Each gap was graded
**solid / mixed / weak** by a verifier that re-fetched sources and rejected unconfirmable claims.

> Only verified claims appear below; every load-bearing claim carries an inline source link, and
> anything that could not be confirmed is marked **(unverified)**. The claims the verifier *threw
> out* are listed in the [Rejected claims](#rejected-claims) appendix — read it to see what didn't
> survive.

## Verification scoreboard

- G1 — DESIGN.md + token-file schema for AI frontend agents: solid (11 verified, 3 rejected)
- G2 — Brief / intent schema: the minimum-viable structured brief for prompting AI frontend generation with aesthetic direction that reliably steers away from generic "AI slop.": mixed (19 verified, 4 rejected)
- G3 — Parallelism: how many competing frontend design candidates to generate, how to enforce diversity, how to present them side-by-side, and the tradeoffs of git worktrees vs parallel subagents vs Stitch .variants() (plus concurrency limits).: mixed (9 verified, 5 rejected)
- G4 — Evaluator protocols (Playwright + human): solid (17 verified, 1 rejected) — +4 (axe-core ~57%/~43% coverage [Deque + axe-core#4415], Playwright vision capability + vision-mode, WCAG 2.2 AA current Rec)
- G5 — Rubric: weights + AI-slop checklist + few-shot. A concrete evaluator rubric for frontend design with criterion weights (design quality, originality, craft, functionality), an actionable AI-slop anti-pattern checklist, and a few-shot calibration format that is both human-readable and machine-scorable.: solid (11 verified, 3 rejected)
- G6 — Critique interchange schema: the canonical critique/feedback record that both a human reviewer can fill by hand and an AI evaluator can emit in a design-competition loop (per-criterion score, rationale, concrete change requests, refine-vs-pivot recommendation).: solid (14 verified, 3 rejected)
- G7 — Stop conditions + anti-fixation for AI design iteration loops (auto/scored vs. human-ship modes), tactics to escape local optima, and verified iteration-count ranges.: solid (13 verified, 2 rejected)
- G8 — Convergence / selection / synthesis: how to pick the winning design among competing frontend candidates, whether/how to synthesize, and how to record the decision.: mixed (15 verified, 5 rejected)
- G9 — Terminology reconciliation: whether "design competition" is the standard term, or whether generator-evaluator / GAN-style harness / best-of-N / LLM-as-judge is the preferred bleeding-edge vocabulary (Anthropic + community, 2026).: mixed (8 verified, 3 rejected)
- G10 — Mode bindings (concrete setup): the exact wiring for Auto/Playwright evaluation (evaluator agent + MCP/tooling) versus Human review (side-by-side surface + critique capture), grounded in real 2026 tools.: solid (15 verified, 4 rejected)

---

### G1 — DESIGN.md + token-file schema

**TL;DR.** Split the design contract into two files with different audiences:

- **`DESIGN.md`** — the *why* and the *rules*: human- and agent-readable prose plus semantic guidance, read *before* generating UI.
- **A tokens file** — the *what*: exact, deterministically-parseable values. Use **W3C DTCG JSON** for design-tool interop, or a **Markdown-table token file** (`designtoken.md` style) / **YAML front matter** if you want everything LLM-native.

Place both at the **project root** so agents auto-load them, and **cross-reference them from `AGENTS.md` / `CLAUDE.md`** — siblings, not competitors: behavior files tell an agent *how to behave and build*; `DESIGN.md` tells an agent *what the product should look like* ([superdesign.dev](https://www.superdesign.dev/blog/what-is-design-md)).

---

#### Where the convention comes from

| Source | Contribution |
|---|---|
| Anthropic **frontend-design plugin** `SKILL.md` | The planning vocabulary: a *compact token system* of **Color** (4–6 named hex values), **Type** (2+ roles — a characterful display face used with restraint, a complementary body face, a utility face for captions/data), **Layout** (one-sentence prose + ASCII wireframes), and **Signature** (the single element the page is remembered by). It tells the agent to do this in its *thinking* and does **not** prescribe a `DESIGN.md` file. ([SKILL.md](https://github.com/anthropics/claude-code/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md)) |
| Anthropic **harness-design** article | The planner was given the frontend design skill, which it "read and used to create a visual design language for the app as part of the spec"; agents communicate via files (one writes, another reads/responds in a file). Example spec sections: Overview, Features, User Stories, Project Data Model. ([anthropic.com](https://www.anthropic.com/engineering/harness-design-long-running-apps)) |
| **cwc-long-running-agents** repo | Machine-readable spec/eval artifacts: Default-FAIL `test-results.json` (features start `{"passes": false}`; a hook blocks writing results without Read evidence), a structured `PROGRESS.md` re-read on every restart, and a no-write evaluator subagent (`agents/evaluator.md`) returning `PASS`/`NEEDS_WORK`. A planner-agent `BUILD_PLAN.md` expanded from a one-line ask is a "Going further" extension, not core. Self-described as "example ingredients, not a turnkey harness." ([repo](https://github.com/anthropics/cwc-long-running-agents)) |
| Google **Stitch → `DESIGN.md`** (VoltAgent `awesome-design-md`) | "DESIGN.md is a new concept introduced by Google Stitch." The prose format is ~9 Markdown sections; "Markdown is the format LLMs read best, so there's nothing to parse or configure." ([awesome-design-md](https://github.com/voltagent/awesome-design-md)) |
| `designtoken.md` | A rigorous Markdown-table **token file** (scales, components, states), one file / zero dependencies, auto-loaded from project root. ([designtoken.md](https://designtoken.md/)) |
| **W3C DTCG** | The interoperable JSON token standard; first stable version (2025.10) announced 28 Oct 2025. ([w3.org](https://www.w3.org/community/design-tokens/2025/10/28/design-tokens-specification-reaches-first-stable-version/)) |

---

#### What goes in `DESIGN.md` (the "why" + semantic rules)

Recommended section order (merge of the Stitch nine sections and the community variant):

1. **Overview / Visual Theme & Atmosphere** — mood, density, brand personality.
2. **Color Palette & Roles** — semantic name + hex + functional role (4–6 named hex values per the frontend-design skill).
3. **Typography Rules** — font families for 2+ roles (display used with restraint, body, utility/data) + a hierarchy table.
4. **Layout Principles** — spacing scale, grid, whitespace; one-sentence concept; ASCII wireframe(s).
5. **Depth & Elevation** — shadow/surface hierarchy.
6. **Component Stylings** — buttons, cards, inputs *with states*.
7. **Signature** — the single unique element the product is remembered by.
8. **Do's and Don'ts** — guardrails / anti-patterns (e.g. "never crowd elements").
9. **Responsive Behavior** — breakpoints, touch targets.
10. **Agent Prompt Guide** — ready-to-use prompts + a token quick reference.

> The Stitch nine sections ([awesome-design-md](https://github.com/voltagent/awesome-design-md)) and the shorter community order — Overview, Colors, Typography, Layout, Elevation and Depth, Shapes, Components, Do's and Don'ts ([superdesign.dev](https://www.superdesign.dev/blog/what-is-design-md)) — differ slightly; both are documented, so treat the order above as a defensible merge rather than a single canonical spec.

> **The "what vs why" split:** an evolved variant keeps both parts in one file — a **YAML front-matter** block of machine-readable tokens at the top, with the Markdown rationale below. The agent "needs a hex code like `#855300`" rather than descriptive language, and the prose covers situations the tokens don't ([departmentofproduct](https://departmentofproduct.substack.com/p/designmd-explained-the-format-reshaping)).

#### What goes in the tokens file (the "what" — exact values)

Pick one:

- **DTCG JSON** — preferred when interop with Figma/Style Dictionary matters. A token is an object whose **`$value` is required**; the **`$type` is optional**, alongside optional `$description`, `$extensions`, and `$deprecated`. It defines composite types (shadow, gradient, border, typography) and supports aliasing via `{colors.blue}` and JSON Pointer `$ref` references ([DTCG 2025.10 spec](https://www.designtokens.org/tr/2025.10/format/)) — letting you layer **primitive** scales under **semantic** roles.
  ```jsonc
  {
    "color": {
      "brand": {
        "600": { "$type": "color", "$value": "#855300", "$description": "primary action" }
      }
    }
  }
  ```
  > Note: `$type` is **optional as an explicit property**, but a token's type must be **resolvable** — explicit, inherited from the nearest parent group's `$type`, or carried via a reference — or the token is **invalid**. So "valid with `$value` alone" holds only when the type resolves from context (DTCG 2025.10 format §type). There is **no official DTCG JSON Schema** yet; build any token-conformance bridge against **Style Dictionary v5** (parses 2025.10 incl. OKLCH) or Terrazzo, not a hand-rolled schema.
- **`designtoken.md` (Markdown tables)** — LLM-native, zero-dependency, auto-loaded from project root: four color roles × 50–900 scale (light/dark computed); a 9-level type scale (size/weight/line-height/letter-spacing); 12-step spacing 4–96px; radius sm/md/lg/xl/full; 5-level shadows + focus-ring/overlay; component tokens with hover/focus states; plus a human-readable visual reference for self-verification ([designtoken.md](https://designtoken.md/)).
- **CSS custom properties** — "CSS variables for everything. All design tokens in one file… A `DESIGN.md` at project root… so every Claude prompt snaps to the same tokens"; restyling becomes changing the token file and rerunning prompts ([thomas-wiegold.com](https://thomas-wiegold.com/blog/claude-code-frontend-design-plugin/)).

**Interop note:** Style Dictionary has first-class DTCG support and is now at **v5** (parses DTCG 2025.10 incl. OKLCH) ([styledictionary.com](https://styledictionary.com/info/dtcg/)), and the DESIGN.md CLI can export tokens to Tailwind v3/v4 and DTCG ([superdesign.dev](https://www.superdesign.dev/blog/what-is-design-md)) — so a DTCG tokens file round-trips with mainstream design tooling. *(Figma native DTCG import/export is slated ~Nov 2026; today via plugins/REST — nice-to-have, not load-bearing.)*

---

#### What makes it machine-readable (checklist for the competition harness)

- **Exact values, not adjectives** — `#855300`, `16px`, `font-weight: 600`, never "warm brown" / "medium" ([departmentofproduct](https://departmentofproduct.substack.com/p/designmd-explained-the-format-reshaping)).
- **Deterministic structure** — DTCG JSON, YAML front matter, or fixed Markdown tables an evaluator can diff.
- **Root placement** — agents auto-load project-root files ([designtoken.md](https://designtoken.md/)).
- **Cross-reference from `AGENTS.md`/`CLAUDE.md`** ([superdesign.dev](https://www.superdesign.dev/blog/what-is-design-md)).
- **Primitive→semantic layering** — DTCG aliasing lets competing designs vary *semantic* role assignments while sharing the *primitive* scale, so variants stay comparable ([DTCG spec](https://www.designtokens.org/tr/2025.10/format/)).
- **Default-FAIL evaluation contract** — pair the design files with a JSON criteria file every variant is graded against (each criterion starts `false`, flips only on Read evidence) and a no-write evaluator subagent returning `PASS`/`NEEDS_WORK`, reusing the same file-based handoff Anthropic's harness uses ([cwc-long-running-agents](https://github.com/anthropics/cwc-long-running-agents)).

**Practical recommendation for a design-competition workflow:** keep `DESIGN.md` + a primitive DTCG token set **constant** as the shared brief; let competing agents vary the *semantic* token mappings, layout, and signature; then score each rendered variant against a Default-FAIL criteria JSON derived from the Do's/Don'ts + token conformance.

> **(unverified)** Whether `DESIGN.md` (prose/semantic) or DTCG JSON (exact values) is the better artifact to hold constant *for a competition specifically*, and how a Playwright/AI evaluator should auto-check rendered CSS custom properties against the token file, are not addressed by any primary source — treat as design judgment, not documented best practice.
> **(unverified)** Meta's "Astryx" (June 2026) was cited as giving agents a readable design system; the source was access-blocked and its schema relative to DTCG could not be confirmed. Do not rely on it.
> **(unverified)** The official `stitch.withgoogle.com` DESIGN.md page is JS-rendered and could not be fetched; the precise canonical Stitch section spec is reported here via the VoltAgent mirror rather than Google's primary page.

---

### G2 — Brief / intent schema

**Bottom line.** "AI slop" is a *distributional-convergence* failure: "models predict tokens based on statistical patterns in training data. Safe design choices–those that work universally and offend no one–dominate web training data," so Claude "samples from this high-probability center," producing "Inter fonts, purple gradients on white backgrounds, and minimal animations" ([Anthropic, Improving frontend design through Skills](https://claude.com/blog/improving-frontend-design-through-skills)). The fix the primary sources converge on is **principle-based direction at the right altitude** — "avoiding the two extremes of low-altitude hardcoded logic like specifying exact hex codes and vague high-altitude guidance" ([Skills blog](https://claude.com/blog/improving-frontend-design-through-skills)) — plus an explicit **negative list** of defaults to reject and a **self-critique pass**. When an evaluator is in the loop, grade on four weighted criteria.

#### Minimum-viable brief (two layers)

> Caveat: no source publishes a formally named/validated brief schema. The field set below is *synthesized* from Anthropic's SKILL.md, the harness-design writeup, and OpenAI's GPT-5.4 guidance, which agree on substance but not on a canonical key set. **(unverified as a standardized schema)**

**Layer 1 — Intent (always required).** When the brief is underspecified the generator must establish clarity itself before designing — *"name one concrete subject, its audience, and the page's single job"*, grounding decisions in the subject's own world rather than defaults ([SKILL.md](https://raw.githubusercontent.com/anthropics/claude-code/main/plugins/frontend-design/skills/frontend-design/SKILL.md)).

| Field | What it captures | Required |
|---|---|---|
| `subject` | One concrete product/subject (not a category) | Yes |
| `audience` | Who it's for | Yes |
| `job` | The page's single job (one primary action/outcome) | Yes |
| `tone` | Mood/personality in one sentence — a "visual thesis: one sentence describing mood, material, and energy" ([OpenAI GPT-5.4](https://developers.openai.com/blog/designing-delightful-frontends-with-gpt-5-4)) | Yes |

**Layer 2 — Aesthetic direction = a compact token system** produced as a first pass *before* code — color, type, layout, signature ([SKILL.md](https://raw.githubusercontent.com/anthropics/claude-code/main/plugins/frontend-design/skills/frontend-design/SKILL.md)):

| Field | Spec | Source |
|---|---|---|
| `color` | The palette "as 4–6 named hex values" | [SKILL.md](https://raw.githubusercontent.com/anthropics/claude-code/main/plugins/frontend-design/skills/frontend-design/SKILL.md) |
| `type` | Multiple roles: "a characterful display face that's used with restraint, a complementary body face, and a utility face for captions or data" | [SKILL.md](https://raw.githubusercontent.com/anthropics/claude-code/main/plugins/frontend-design/skills/frontend-design/SKILL.md) |
| `layout` | One-sentence concept + ASCII wireframes | [SKILL.md](https://raw.githubusercontent.com/anthropics/claude-code/main/plugins/frontend-design/skills/frontend-design/SKILL.md) |
| `motion` | Motion *philosophy*, not effects: "at least 2-3 intentional motions for visually led work," used "to create presence and hierarchy, not noise" | [OpenAI GPT-5.4](https://developers.openai.com/blog/designing-delightful-frontends-with-gpt-5-4) |
| `signature` | "the single unique element this page will be remembered by" — spend boldness in *one* place | [SKILL.md](https://raw.githubusercontent.com/anthropics/claude-code/main/plugins/frontend-design/skills/frontend-design/SKILL.md) |
| `references` | Evocative, non-prescriptive: "Draw from IDE themes and cultural aesthetics for inspiration" | [Skills blog](https://claude.com/blog/improving-frontend-design-through-skills) |
| `avoid` | Explicit negative list of convergent defaults (below) | [Skills blog](https://claude.com/blog/improving-frontend-design-through-skills) |

The four design dimensions Anthropic guides on are **Typography, Color & Theme, Motion, Backgrounds** ([Skills blog](https://claude.com/blog/improving-frontend-design-through-skills)). *(The earlier framing of "three named strategies" is **not** in the source and has been dropped.)*

#### The `avoid` list (what defeats slop)
- Overused fonts — **"Never use: Inter, Roboto, Open Sans, Lato, default system fonts"** ([Skills blog](https://claude.com/blog/improving-frontend-design-through-skills)); OpenAI's variant is "avoid default stacks (Inter, Roboto, Arial, system)" ([OpenAI GPT-5.4](https://developers.openai.com/blog/designing-delightful-frontends-with-gpt-5-4)). *(Arial is in OpenAI's list, not Anthropic's.)*
- **Purple gradients on white backgrounds** ([Skills blog](https://claude.com/blog/improving-frontend-design-through-skills)); "purple gradients over white cards" as a telltale AI sign ([Anthropic harness design](https://www.anthropic.com/engineering/harness-design-long-running-apps)); "avoid purple-on-white defaults" ([OpenAI GPT-5.4](https://developers.openai.com/blog/designing-delightful-frontends-with-gpt-5-4)).
- **Card-heavy layouts** — reject the "generic SaaS card grid" ([OpenAI GPT-5.4](https://developers.openai.com/blog/designing-delightful-frontends-with-gpt-5-4)). *Note: the specific "three-card feature grid" is **not** mentioned in the Anthropic Skills blog; the card-grid caution is sourced to OpenAI.*
- The three SKILL.md default clusters that are *themselves* now AI-slop: (1) warm cream `#F4F1EA` + serif display + terracotta accent; (2) near-black + acid-green or vermilion accent; (3) "broadsheet-style layout with hairline rules, zero border-radius, and dense newspaper-like columns" ([SKILL.md](https://raw.githubusercontent.com/anthropics/claude-code/main/plugins/frontend-design/skills/frontend-design/SKILL.md)).

#### Mandatory self-critique pass
Before writing code, review the design plan against the brief to confirm it is specific to *this* project — not a default solution recycled across similar briefs — and revise accordingly; only then write code ([SKILL.md](https://raw.githubusercontent.com/anthropics/claude-code/main/plugins/frontend-design/skills/frontend-design/SKILL.md)). *(The verbatim phrasing "reads like the generic default you would produce for any similar page rather than a choice made for this specific brief" is a paraphrase — the substance is verified; the exact quote string is **(unverified)**.)*

#### Evaluator grading rubric (for the competition loop)
Anthropic's generator-evaluator harness grades on four criteria, weighting **design quality + originality above craft + functionality** "since Claude already scored well on craft and functionality by default"; the evaluator drives live pages via the **Playwright MCP** "before scoring each criterion and writing a detailed critique," over "5 to 15 iterations per generation" ([Anthropic harness design](https://www.anthropic.com/engineering/harness-design-long-running-apps)):
1. **Design quality** — "Does the design feel like a coherent whole rather than a collection of parts?"
2. **Originality** — "evidence of custom decisions" vs. "template layouts, library defaults, and AI-generated patterns."
3. **Craft** — "typography hierarchy, spacing consistency, color harmony, contrast ratios."
4. **Functionality** — "Usability independent of aesthetics... find primary actions, and complete tasks without guessing."

Tip from the harness: prompt phrasing steers convergence — "the best designs are museum quality" steered the generator in unanticipated ways — and the evaluator was calibrated with "few-shot examples with detailed score breakdowns" ([harness design](https://www.anthropic.com/engineering/harness-design-long-running-apps)).

#### Example brief (drop-in YAML)
```yaml
# Layer 1 — intent
subject: "Klang — a boutique vinyl mastering studio in Rotterdam"
audience: "independent musicians and small labels evaluating a mastering partner"
job: "get the visitor to book a mastering consultation"
tone: "analog warmth meets engineering precision — tactile, confident, unhurried"

# Layer 2 — aesthetic direction (token system)
color:        # 4-6 named hex
  bg:      "#0E0B08"
  surface: "#1A1512"
  text:    "#F2E9DC"
  muted:   "#8A7C6A"
  accent:  "#D8531F"   # signal orange, used once
type:
  display: "GT Sectra (high-contrast, characterful — restraint)"
  body:    "Söhne (neutral, highly readable)"
  utility: "Söhne Mono (specs, timecodes, data)"
layout: "Single full-bleed waveform spanning the hero; sections snap to its peaks. [ ASCII wireframe ]"
motion: "2-3 motions only: waveform scrubs on scroll, accent pulses on the single CTA; no decorative parallax"
signature: "A live, scrubbable mastering waveform that doubles as the page's spine and navigation"
references: ["1970s tape-machine VU meters", "Teenage Engineering hardware restraint"]
avoid: ["Inter/Roboto/Open Sans/Lato/system fonts", "purple-on-white gradients",
        "generic SaaS card grid", "cream+terracotta+serif default",
        "near-black + acid-green default", "broadsheet/hairline default"]
```

*Example values are illustrative, not sourced.*

#### Open questions (carried forward)
- No source publishes a formally validated/named brief schema; the key set above is synthesized. **(unverified)**
- Whether the negative `avoid` list quantitatively outperforms positive direction alone is described qualitatively (distributional convergence) but **not benchmarked** in the public sources. **(unverified)**
- The optimal split of human-authored vs. model-auto-generated brief fields for a competition harness is unspecified; sources only give the model's "pin it yourself" heuristic. **(unverified)**

---

### G3 — Parallelism: N candidates + diversity

**TL;DR.** The strongest, source-backed move is to keep two loops separate: a **fan-out layer** (generate several diverse candidates, screen them, keep one) sitting in front of Anthropic's **single-track generator/evaluator deep-iteration loop**. A small candidate count (≈3, up to 5) is supported by *tool defaults* but **not** by the quality benchmarks originally cited — treat "3–5" as a sensible default, not a proven optimum. Enforce diversity deliberately (assigned directions / personas / seeds), present candidates as a screenshot grid, then deep-iterate only the winner.

#### Two loops — don't conflate them
Anthropic's production harness ("Harness design for long-running apps") is **not** a parallel-candidate system. It runs **one generator + one evaluator** over **5–15 sequential iterations**, with "each iteration typically pushing the generator in a more distinctive direction as it responded to the evaluator's critique." The evaluator was given the **Playwright MCP** to "interact with the live page directly before scoring each criterion," grading on four axes — **design quality, originality, craft, functionality** — and the design is explicitly GAN-inspired: "separating the agent doing the work from the agent judging it proves to be a strong lever." ([Anthropic](https://www.anthropic.com/engineering/harness-design-long-running-apps))

Parallelism (N competing candidates) is therefore a **practitioner layer that sits in front of** that loop: fan out N diverse candidates → screen side-by-side → keep the winner → hand it to the 5–15-iteration generator/evaluator loop. Treating fan-out and deep-iteration as one budget is the main anti-pattern.

#### How many candidates: ≈3 (up to 5) — on weaker evidence than first claimed
What is verifiable is that **3 is the common tool default**, with **5 as a ceiling** in the design-exploration tooling:
- **Stitch `variants()` defaults to 3, max 5.** ([stitch-sdk](https://github.com/google-labs-code/stitch-sdk))
- **parallel-worktrees defaults to 3 agents.** ([parallel-worktrees](https://github.com/spillwavesolutions/parallel-worktrees))

The two "convergent benchmark" pillars originally offered for a 3–5 *quality* sweet spot did **not** survive verification:
- **(unverified) "Best-of-N quality saturates by N≈4."** The cited paper (arxiv 2507.08944) is about parallel multi-agent *teams* for speedup, not best-of-N saturation; it does not support an N≈4 quality knee.
- **(unverified) "Multi-critic diversity saturates at ≈3" / "raw idea diversity plateaus at 20–30."** Neither number appears in the cited diversity paper (arxiv 2602.20408).

So: use **N=3** as a default and **N=5** for genuinely open visual briefs, but justify it as "tool-default + review-bandwidth," not as a proven optimum. The binding constraint in practice is human/judge review: practitioners report "Five to ten parallel agents works well for most devs. Past ten, the merge step is the bottleneck, not the build step" (incident.io runs four to seven per developer). ([botmonster](https://botmonster.com/posts/parallel-ai-development-claude-code-sessions-git-worktrees/))

#### Enforcing diversity (deliberate, not emergent)
Independent LLM samples **converge without intervention** — the diversity literature attributes this to *fixation* (early outputs constrain later ideation) and *knowledge aggregation*, and shows that interventions like chain-of-thought prompting and assigning **ordinary personas** anchor generation in distinct regions of semantic space and raise diversity. ([arxiv 2602.20408](https://arxiv.org/abs/2602.20408)) Practical levers:
1. **Assign each candidate a distinct strategic/aesthetic direction and persona** rather than relying on temperature alone. ([arxiv 2602.20408](https://arxiv.org/abs/2602.20408))
2. **Stitch-native:** set `creativeRange: "REIMAGINE"` and target specific `aspects` (`LAYOUT`, `COLOR_SCHEME`, `TEXT_FONT`, …) to force divergence along chosen dimensions. ([stitch-sdk](https://github.com/google-labs-code/stitch-sdk))
3. **Non-determinism as a (weak) source:** parallel-worktrees "exploits LLM non-determinism as a feature: running N parallel agents gives you N valid solutions to choose from." ([parallel-worktrees](https://github.com/spillwavesolutions/parallel-worktrees))

Caveat: the frontend-design SKILL preaches **depth over breadth** — one committed direction per brief ("Spend your boldness in one place"). So use fan-out to pick a *direction*, then switch the winner into single-track depth mode. ([SKILL.md](https://github.com/anthropics/claude-code/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md))

> **(unverified)** The earlier claim that this SKILL ships a ready-made "tone" taxonomy (brutalist / luxury / playful / maximalist / art-deco / …) and a four-question (purpose, tone/audience, constraints, differentiation) framework to assign one tone per candidate is **not** in the source. The SKILL uses a 3-part grounding (name the subject, its audience, the page's single job) and mentions "maximalist/minimal/brutalist/editorial" only in passing — three of those as AI defaults to *avoid*. If you want a tone menu to assign across candidates, author it yourself; do not attribute it to the SKILL.

#### Presenting candidates side-by-side
Capture each candidate with Playwright — full page via `page.screenshot()` ("a screenshot of a full scrollable page") or per-component via `locator.screenshot()` — and tile them into a grid. ([Playwright](https://playwright.dev/docs/screenshots)) Review options:
- **Human pick:** scan the grid, choose one.
- **AI judge (cheap):** score the grid from screenshots only.
- **AI judge (thorough):** evaluator drives each live candidate via Playwright MCP and scores the four criteria — accurate but multiplies cost by N. ([Anthropic](https://www.anthropic.com/engineering/harness-design-long-running-apps))

> **(unverified)** That "Playwright's HTML reporter shows the candidate images side by side" is not stated on the screenshots docs page; build the contact sheet yourself (e.g. tile the captured PNGs into one HTML page) rather than assuming the reporter does it.

#### Mechanism tradeoffs

| Mechanism | Best for | Diversity source | Concurrency / cost | Key limits |
|---|---|---|---|---|
| **git worktrees** (`claude --worktree`, or subagent `isolation: worktree`) | Full-app candidates needing isolated file trees + branches | Non-determinism + per-track prompts | ~5–10 reliable/dev before merge bottleneck; **~15x tokens** vs single | Isolate files only; need per-tree env setup; share one `.git`. ([worktrees](https://code.claude.com/docs/en/worktrees), [parallel-worktrees](https://github.com/spillwavesolutions/parallel-worktrees), [botmonster](https://botmonster.com/posts/parallel-ai-development-claude-code-sessions-git-worktrees/)) |
| **parallel subagents** (in-session fan-out) | Component/page candidates inside one session | Assigned directions per subagent | **(unverified)** exact cap min(16, cpu_cores−2) is **not** confirmed by any source | **Subagents can't spawn subagents** (no nesting). ([parallel-worktrees](https://github.com/spillwavesolutions/parallel-worktrees)) |
| **Stitch `.variants()`** (API) | Pure screen-level design exploration | `variantCount` 1–5, `creativeRange`, `aspects` | Up to 5/call; Gemini-backed | Screen-level not full-app; cross-tool quality may not match a Claude/Playwright pipeline. ([stitch-sdk](https://github.com/google-labs-code/stitch-sdk)) |

`variants()` shape: `screen.variants(prompt, { variantCount: 3, creativeRange: "EXPLORE", aspects: ["COLOR_SCHEME","LAYOUT"] }, deviceType?, modelId?)` → `Screen[]`, each with `getImage()` and `getHtml()` for the contact sheet. ([stitch-sdk](https://github.com/google-labs-code/stitch-sdk))

> **(unverified)** Concurrency ceiling: the specific `min(16, cpu_cores − 2)` cap and "hard ceiling of 16, not user-configurable" could not be confirmed in any source (the cited mindstudio.ai page only says limits are configurable in settings). Do not encode that exact formula in the spec; verify against Claude Code's own docs/release notes before relying on it. Claude Code does, however, document worktree-backed isolation and `isolation: worktree` subagent frontmatter that is cleaned up automatically when the subagent finishes without changes. ([worktrees](https://code.claude.com/docs/en/worktrees))

#### Recommended default
`N=3` candidates, each pinned to a distinct assigned direction + persona (and distinct seed) → run as subagents (or worktrees if each is a full app) → assemble a Playwright screenshot grid → human or AI judge picks one → winner enters the **5–15-iteration generator/evaluator loop** with Playwright-MCP scoring on the four criteria (design quality, originality, craft, functionality). ([Anthropic](https://www.anthropic.com/engineering/harness-design-long-running-apps), [SKILL.md](https://github.com/anthropics/claude-code/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md), [Playwright](https://playwright.dev/docs/screenshots))

**Open items (no primary source):** (1) whether fan-out-then-deep-iterate beats single-track 5–15 iterations for frontend quality is unbenchmarked; (2) the right compute split (e.g. 4 candidates × 3 cheap screening passes, then 1 winner × 10–15 deep passes) is unmeasured; (3) screenshot-only vs live-Playwright judging tradeoff for grids is unquantified; (4) whether Stitch `.variants()` output interoperates cleanly as a candidate source feeding a Claude/Playwright evaluator is untested.

---

### G4 — Evaluator protocols (Playwright + human)

Both seats consume the **same inputs** (a running build at a local URL + the design spec) and emit the **same output shape** (a per-criterion critique with a verdict/score and prioritized findings), so an AI evaluator and a human reviewer are drop-in interchangeable in the iteration loop.

#### A. AI evaluator seat (Playwright MCP) — Anthropic GAN-style harness

Source of truth: Anthropic, *[Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)*, and the companion repo [`anthropics/cwc-long-running-agents`](https://github.com/anthropics/cwc-long-running-agents).

- **Topology:** A GAN-inspired **generator / evaluator** split — "separating the agent doing the work from the agent judging it" — chosen because agents otherwise "confidently praise the work—even when… the quality is obviously mediocre" ([Anthropic](https://www.anthropic.com/engineering/harness-design-long-running-apps)). In the repo the evaluator is a **fresh-context subagent with no Write/Edit tools** that reviews the diff and screenshots "from a context window that never saw the build," invoked via `claude --agent evaluator -p "<review prompt>"` and returning `PASS` / `NEEDS_WORK` with specific findings ([`cwc-long-running-agents`](https://github.com/anthropics/cwc-long-running-agents)).
- **Inspection method — live interaction, not static screenshots:** the evaluator was given the **Playwright MCP**, which "let it interact with the live page directly before scoring each criterion and writing a detailed critique. In practice, the evaluator would navigate the page on its own, screenshotting and carefully studying the implementation before producing its assessment" ([Anthropic](https://www.anthropic.com/engineering/harness-design-long-running-apps)). This is an explicit **opt-in "browser-verified evaluator"** pattern: add [`@playwright/mcp`](https://github.com/microsoft/playwright-mcp) (microsoft/playwright-mcp) or Claude in Chrome to `tools:` in `agents/evaluator.md` so the evaluator opens the running app instead of trusting the builder's screenshots ([`cwc-long-running-agents`](https://github.com/anthropics/cwc-long-running-agents)).
- **Rubric (four gradable principles, few-shot calibrated, not pass/fail):** ([Anthropic](https://www.anthropic.com/engineering/harness-design-long-running-apps))
  1. **Design Quality** — "Does the design feel like a coherent whole rather than a collection of parts?"
  2. **Originality** — custom decisions vs. template layouts, library defaults, and AI-generated patterns
  3. **Craft** — typography hierarchy, spacing consistency, color harmony, contrast ratios
  4. **Functionality** — usability independent of aesthetics

  Weighting: the author "emphasized design quality and originality over craft and functionality" (Claude already scored well on craft/functionality by default). Calibration used "few-shot examples with detailed score breakdowns," which aligned judgment and "reduced score drift across iterations." The rubric is **deliberately not shipped** in the repo because it is project-specific ([`cwc-long-running-agents`](https://github.com/anthropics/cwc-long-running-agents)).
- **Loop:** "5 to 15 iterations per generation"; the critique feeds the generator, which makes "a strategic decision after each evaluation: refine the current direction if scores were trending well, or pivot to an entirely different aesthetic if the approach wasn't working." Because evaluation is live navigation, "full runs stretched up to four hours." Scores did not improve cleanly/linearly — the author "regularly saw cases where I preferred a middle iteration over the last one"; no formal human-validation protocol is described ([Anthropic](https://www.anthropic.com/engineering/harness-design-long-running-apps)).
- **Human override hooks:** `hooks/kill-switch.sh` halts every tool call while an `AGENT_STOP` file exists at the project root; `hooks/steer.sh` surfaces `STEER.md` contents to the agent once then clears it, for mid-run redirection ([`cwc-long-running-agents`](https://github.com/anthropics/cwc-long-running-agents)).

#### B. Human reviewer seat — design-review protocol (interchangeable)

The community [design-review subagent protocol](https://github.com/EricTechPro/match-me/blob/main/.claude/agents/design-review-agent.md) is the human-readable mirror of the same seat — a human follows these phases, or the identical prompt drives an AI reviewer.

- **Principle: "Live Environment First"** — "always assessing the interactive experience before diving into static analysis or code." Feedback follows **"Problems Over Prescriptions"**: e.g., instead of "Change margin to 16px," say "The spacing feels inconsistent with adjacent elements, creating visual clutter," backed by screenshot evidence.
- **Phases (eight: Phase 0 through Phase 7 — note the finding's "seven" is inaccurate):**
  - **0. Preparation** — open a Playwright preview (default 1440×900)
  - **1. Interaction & User Flow**
  - **2. Responsiveness Testing** — **Desktop 1440px · Tablet 768px · Mobile 375px**
  - **3. Visual Polish**
  - **4. Accessibility (WCAG 2.2 AA)** — including color contrast **≥ 4.5:1** *(WCAG 2.2 is the current W3C Recommendation, first published 5 Oct 2023, now an **edited Recommendation dated 12 December 2024** — status/contrast unaffected; the harness targets 2.2 AA, superseding the 2.1 AA the source protocol named)*
  - **5. Robustness Testing**
  - **6. Code Health**
  - **7. Content & Console**
- **Triage matrix (shared output vocabulary):** `[Blocker]` → `[High-Priority]` → `[Medium-Priority]` → `[Nitpick]`.

> Supporting plugin: the official [`frontend-design` plugin](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/frontend-design) (authors Prithvi Rajasekaran and Alexander Bricken) "generates distinctive, production-grade frontend interfaces that avoid generic AI aesthetics" and points to the [Frontend Aesthetics Cookbook](https://github.com/anthropics/claude-cookbooks/blob/main/coding/prompting_for_frontend_aesthetics.ipynb). Its README does **not** ship viewport, rubric, or MCP config — those live in the harness docs above.

#### C. Making the seats interchangeable (design-competition wiring)

- Pin a **fixed viewport set** for both seats (1440 / 768 / 375) so AI and human scores are comparable; default scoring viewport 1440×900. *(Note: this viewport set comes from the community design-review protocol; the Anthropic GAN post does not name a scoring viewport — see unverified items below.)*
- Both write to the **same critique artifact** (per-criterion score + triaged findings) so the generator can't tell which seat produced it.
- Keep the evaluator **write-locked and fresh-context** in both modes — the human reviews the running app, never edits it, matching the AI evaluator's no-Write/Edit constraint.
- For an AI seat, enforce **live interaction before screenshot capture**; for a human seat, enforce **Live Environment First** — same ordering, same evidence trail.

#### Unverified / not published

- **(unverified)** The exact Playwright MCP server config block Anthropic used for the evaluator (allowed-tools list, headless flag, isolated profile) — the repo only instructs adding `@playwright/mcp` to `tools:` in `agents/evaluator.md`.
- **(unverified)** Whether the Anthropic evaluator pins a fixed scoring viewport — the design article does not name one; the 1440/768/375 set is from the community design-review subagent, not the GAN harness post.
- **(unverified)** The verbatim few-shot rubric / score breakdowns used to calibrate the evaluator — deliberately not shipped because project-specific.

#### D. Accessibility floor is necessarily PARTIAL (axe-core coverage) — VERIFIED

The harness gates on an automated accessibility floor computed by axe-core. That floor cannot be "WCAG-complete" because automated tooling only catches part of the issue volume; the remainder needs human judgment. This is the evidentiary basis for invariant 7's "partial floor" framing and for the human seat's advisory 43%-class change_requests.

- **Deque automated-coverage report** — "On average across all the audits included in the sample data, we found that **57.38% of total issues** were identified using Deque's automated tests" — i.e. **~42.62% require manual testing**, measured across 13,000+ pages / ~300,000 issues. The report explicitly argues this *replaces* the older "20–30% of Success Criteria" framing by counting issue *volume* rather than criteria count ([Deque, *Automated Accessibility Coverage Report*](https://www.deque.com/automated-accessibility-coverage-report/), fetched 2026-06-28).
- **axe-core repository / issue #4415** — the axe-core repo states "**With axe-core, you can find on average 57% of WCAG issues automatically**," and the tool additionally flags items as "incomplete" where manual review is required. Issue #4415 documents the inconsistency between this repo figure (57%) and the DevTools marketing figure (80%) ([dequelabs/axe-core#4415](https://github.com/dequelabs/axe-core/issues/4415), fetched 2026-06-28). Harness consequence: gated floor keys are the axe-checkable subset (responsive_*, visible_keyboard_focus, contrast_AA_4_5); the ~43% (logical focus order, meaningful alt text, 2.4.11 focus-not-obscured, much of 2.5.8) enter only as advisory, non-gating change_requests.

#### E. Vision-grounded judging — Playwright MCP vision capability — VERIFIED

Design_quality/originality cannot be scored from the DOM/accessibility tree alone (invariant 8), so the rendered screenshot must be in the judging context. The relevant Playwright MCP semantics:

- **Capabilities** — `--caps=vision` enables "**Coordinate-based mouse tools for screenshot-driven workflows. Requires a vision-capable LLM**" (six tools: `browser_mouse_click_xy`, `browser_mouse_drag_xy`, `browser_mouse_wheel`, etc.). The default capability set uses **accessibility snapshots**, not coordinates ([Playwright MCP — Capabilities](https://playwright.dev/mcp/capabilities), fetched 2026-06-28).
- **Vision mode** — "Vision mode adds coordinate-based tools that work with screenshots… For most web applications, the default snapshot-based approach is more reliable and token-efficient. Use vision mode only when the accessibility tree doesn't cover your use case" ([Playwright MCP — Vision Mode](https://playwright.dev/mcp/vision-mode), fetched 2026-06-28).
- Harness consequence: omitting `--caps=vision` is fine — it only drops the coordinate-click tools. `browser_take_screenshot` still returns the image, which the wrapper injects into the judging prompt as an image block; the evaluator/generator models must be multimodal. (The "requires a vision-capable LLM" note applies to the *coordinate tools*, not to receiving a screenshot in context.)

---

### G5 — Rubric: weights + AI-slop checklist + few-shot

**Source of truth.** Anthropic's [*Harness design for long-running application development*](https://www.anthropic.com/engineering/harness-design-long-running-apps) defines the canonical four-criterion frontend rubric and the weighting *direction*. It deliberately does **not** publish exact numeric weights, a score scale, a JSON schema, or few-shot template text. Everything below that carries numbers, schemas, or example scores is an **(unverified) recommended implementation**, not an Anthropic figure. The anti-pattern content is grounded in the official `frontend-design` SKILL.md plus practitioner corroboration where noted.

#### Criteria and definitions (verified)

The evaluator uses **exactly four** grading criteria, defined verbatim in the post ([Anthropic](https://www.anthropic.com/engineering/harness-design-long-running-apps)):

- **Design quality** — "Does the design feel like a coherent whole rather than a collection of parts? ... the colors, typography, layout, imagery ... combine to create a distinct mood and identity." (creativity axis)
- **Originality** — "Is there evidence of custom decisions, or is this template layouts, library defaults, and AI-generated patterns?" Unmodified stock components and "telltale signs of AI generation like purple gradients over white cards" fail here. (creativity axis)
- **Craft** — "typography hierarchy, spacing consistency, color harmony, contrast ratios. This is a competence check rather than a creativity check." (competence axis)
- **Functionality** — "Usability independent of aesthetics. Can users understand what the interface does, find primary actions, and complete tasks without guessing?" Verified by the evaluator via Playwright MCP interaction ([Anthropic](https://www.anthropic.com/engineering/harness-design-long-running-apps); [InfoQ](https://www.infoq.com/news/2026/04/anthropic-three-agent-harness-ai/)). (competence axis)

**Weighting direction (verified):** Anthropic "emphasized design quality and originality over craft and functionality" because "Claude already scored well on craft and functionality by default," and "the criteria explicitly penalized highly generic 'AI slop' patterns" ([Anthropic](https://www.anthropic.com/engineering/harness-design-long-running-apps)). The marginal signal therefore lives on the creative axes.

#### Recommended weights and scoring (unverified — implementation choice)

The split, scale, and aggregation below **(unverified — not published by Anthropic)** encode the verified direction:

| Criterion | Weight *(unverified)* | Axis |
|---|---|---|
| Design quality | 0.35 | creativity |
| Originality | 0.35 | creativity |
| Craft | 0.20 | competence |
| Functionality | 0.10 | competence |

- Score each criterion **0–10** *(unverified scale)*; aggregate `round((dq*0.35 + orig*0.35 + craft*0.20 + func*0.10) * 10)` → 0–100 *(unverified)*.
- **Gating rule (unverified recommendation):** any criterion < 4 caps the aggregate at 49 so a beautiful-but-unusable page cannot pass on weighted average alone. Whether Anthropic uses hard gating vs. pure weighted average is **unconfirmed**.

#### Machine-scorable evaluator output schema (unverified — recommendation)

Anthropic has not published the evaluator's output schema. The following is a recommended shape only:

```json
{
  "iteration": 3,
  "variant": "B",
  "scores": { "design_quality": 0, "originality": 0, "craft": 0, "functionality": 0 },
  "weighted_total": 0,
  "verdict": "iterate",
  "ai_slop_flags": ["string"],
  "blocking_issues": ["string"],
  "critique": "string",
  "evidence": { "screenshots": ["string"], "playwright_findings": ["string"] }
}
```

Suggested verdict thresholds **(unverified):** `>=80 && no blocking_issues` → ship; `50–79` → iterate; `<50 || gated` → reject.

#### AI-slop anti-pattern checklist

**Default look-clusters — verified, from SKILL.md** ([SKILL.md](https://github.com/anthropics/claude-code/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md)). Flag when chosen by default rather than by brief:
- `cluster-cream-serif` — "a warm cream background (near #F4F1EA) with a high-contrast serif display and a terracotta accent."
- `cluster-dark-acid` — "a near-black background with a single bright acid-green or vermilion accent."
- `cluster-broadsheet` — "a broadsheet-style layout with hairline rules, zero border-radius, and dense newspaper-like columns."

**Behavioral / content tells — verified, from SKILL.md** ([SKILL.md](https://github.com/anthropics/claude-code/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md)):
- `motion-scatter` — extra animation "contributes to the feeling that the design is AI-generated."
- `numbered-markers` — `01 / 02 / 03` markers are only justified when "the content actually is a sequence."
- `copy-templated` — poorly considered copy can make a design feel as generic/templated as the visuals.

**Typography / color / layout tells — practitioner corroboration only (NOT in current SKILL.md):** Inter / Roboto / Arial / system fonts and Space Grotesk (the overused "anti-Inter" default), purple-indigo gradients on white, three cards in a row, uniform border-radius, and shadows "at exactly 0.1 opacity" are called out in practitioner writeups ([thomas-wiegold.com](https://thomas-wiegold.com/blog/claude-code-frontend-design-plugin/); [paddo.dev](https://paddo.dev/blog/claude-code-plugins-frontend-design/)). The current fetched SKILL.md does **not** enumerate banned fonts or the 0.1-opacity detail; treat these as community lore and confirm against the SKILL version your harness pins.

**Positive levers — practitioner corroboration** ([paddo.dev](https://paddo.dev/blog/claude-code-plugins-frontend-design/)): distinctive typography over safe defaults, dominant color with sharp accents over timid palettes, atmospheric depth over flat backgrounds, and asymmetric composition over predictable grids.

#### Few-shot calibration (method verified; example numbers unverified)

**Verified method:** use a separate evaluator agent (GAN-inspired generator/evaluator split) "calibrated ... using few-shot examples with detailed score breakdowns," which "ensured the evaluator's judgment aligned with my preferences, and reduced score drift across iterations" ([Anthropic](https://www.anthropic.com/engineering/harness-design-long-running-apps); separation as the bias lever corroborated by [InfoQ](https://www.infoq.com/news/2026/04/anthropic-three-agent-harness-ai/) and [understandingdata.com](https://understandingdata.com/posts/generator-evaluator-harness-design/)).

**Verified failure mode to anchor against:** early evaluators would "identify legitimate issues, then talk itself into deciding they weren't a big deal and approve the work anyway" ([Anthropic](https://www.anthropic.com/engineering/harness-design-long-running-apps)); restated in [understandingdata.com](https://understandingdata.com/posts/generator-evaluator-harness-design/). Note: in the Anthropic post this exact phrasing describes the full-stack QA evaluator, and is the rationale for strict, calibrated anchors.

**(unverified) example format** — the anchor text, scores, and IDs below are illustrative only; Anthropic has not published its few-shot examples:

```
EXAMPLE — verdict: reject (weighted_total 38)   [unverified illustration]
design_quality: 4 — coherent but generic; mood reads as "AI default", not this brief.
originality: 2 — Inter + purple-on-white gradient + three icon cards.
craft: 7 — spacing/contrast fine; competent.
functionality: 8 — primary CTA discoverable, tasks completable.
why: high competence cannot offset originality=2. Do not rationalize the slop flags away.
```

Provide ≥1 anchor per band, keep a rationale field that explicitly instructs the evaluator not to talk itself out of fired flags, and re-run the same few-shot set every iteration so scores stay comparable.

#### Open caveats
- The 0.35/0.35/0.20/0.10 weights, 0–10 scale, gating rule, verdict thresholds, JSON schema, and all few-shot example scores are **unverified recommendations** — only the four criteria, their definitions, the design+originality > craft+functionality direction, the few-shot-with-breakdowns calibration method, the Playwright-MCP evaluator, and the three default look-clusters are sourced.
- The banned-font list (Inter/Roboto/Arial/Space Grotesk) and 0.1-opacity shadow are practitioner-attributed and absent from the current SKILL.md; pin and re-verify your SKILL version.

---

### G6 — Critique interchange schema

**Goal.** One critique record that a human reviewer can fill in by hand and an AI evaluator (e.g. a Playwright-driven Claude judge) can emit verbatim, so the design-competition loop treats both sources identically.

> **Provenance note.** Anthropic has **not** published a single literal JSON critique schema for its design evaluator. The four-criterion rubric, the refine/pivot decision, and the verdict format are documented in prose and in the shipped reference harness; the JSON record below is a **synthesis** of those primary sources plus the standard LLM-as-judge structured-output convention — not a copied Anthropic artifact.

#### Design principles (from primary sources)

- **Fixed criterion set, not free-form prose.** Anthropic's frontend evaluator scores every design on exactly four dimensions — **design quality, originality, craft, functionality** — and deliberately emphasized *design quality + originality* over *craft + functionality* for frontend work. ([anthropic.com](https://www.anthropic.com/engineering/harness-design-long-running-apps)) These map to concrete measures: design quality = coherence/mood/unified identity; originality = custom decisions vs template/AI-slop patterns; craft = typography hierarchy, spacing, color harmony, contrast ratios; functionality = comprehension, task completion, action discoverability. ([understandingdata.com](https://understandingdata.com/posts/generator-evaluator-harness-design/))

- **Per-criterion gating, not an average.** Anthropic's harness used *hard thresholds* — each criterion has a floor, and if any one falls below it the sprint fails and the generator gets detailed feedback, rather than letting a strong average hide one broken dimension. Note: this gating mechanism is documented for Anthropic's multi-agent **coding/full-stack** harness; applying it to the *design* critique is a deliberate transfer, since the design evaluator itself is described as producing scores + a refine/pivot decision. ([anthropic.com](https://www.anthropic.com/engineering/harness-design-long-running-apps))

- **Every finding is evidence-bound.** Findings are anchored to concrete evidence — a screenshot, a `git diff`, or a code location with an exact diagnosis (the secondary summary cites `LevelEditor.tsx:892` paired with a FAIL verdict as an illustrative example). The shipped evaluator's rule is blunt: "Plausibility is not correctness," a file that fails to open is treated as missing evidence, and missing evidence for any acceptance criterion is `NEEDS_WORK`. ([understandingdata.com](https://understandingdata.com/posts/generator-evaluator-harness-design/), [github.com/anthropics/cwc-long-running-agents](https://github.com/anthropics/cwc-long-running-agents/blob/main/claude-code-config/.claude/agents/evaluator.md))

- **The critique must carry the next move.** Anthropic's generator branch is explicit: *refine* the current direction if scores were trending well, or *pivot* to an entirely different aesthetic if the approach wasn't working. So `recommendation` is a required field. ([anthropic.com](https://www.anthropic.com/engineering/harness-design-long-running-apps))

- **Findings are the next prompt.** In the shipped harness the verdict + bulleted findings list is the builder's next-session starting prompt, so `change_requests` must be specific and actionable, not vague. ([github.com/anthropics/cwc-long-running-agents](https://github.com/anthropics/cwc-long-running-agents/blob/main/claude-code-config/.claude/agents/evaluator.md))

#### Canonical critique record (JSON interchange — synthesized, see provenance note)

```json
{
  "candidate_id": "design-B",
  "round": 2,
  "evaluator": { "type": "ai", "id": "claude-judge", "method": "playwright+screenshot" },
  "verdict": "NEEDS_WORK",
  "scores": {
    "design_quality": { "score": 4, "rationale": "Coherent whole; hero mood lands, but footer reads like a different site." },
    "originality":    { "score": 2, "rationale": "Warm-cream + serif + terracotta is a generic AI-slop default; no custom decisions." },
    "craft":          { "score": 4, "rationale": "Type hierarchy clean; body/caption contrast fails AA at 3.8:1." },
    "functionality":  { "score": 5, "rationale": "Primary CTA discoverable; task path completes." }
  },
  "overall": 3.5,
  "quality_floor": { "responsive_mobile": true, "visible_keyboard_focus": false, "reduced_motion": true },
  "change_requests": [
    { "criterion": "originality", "expected": "A signature element specific to this brief",
      "observed": "Generic terracotta accent palette", "evidence": "screenshot:home@1280.png",
      "severity": "blocker", "fix": "Replace palette with a brief-specific direction; commit to one bold signature move." },
    { "criterion": "craft", "expected": "WCAG AA contrast on body text", "observed": "3.8:1",
      "evidence": "styles/tokens.css:42", "severity": "major", "fix": "Darken --color-body to meet 4.5:1." }
  ],
  "recommendation": "refine",
  "recommendation_rationale": "Craft/quality/functionality trending well; only originality is failing — fixable without abandoning the direction.",
  "confidence": "high"
}
```

#### Field reference

| Field | Type | Fillable by | Notes |
|---|---|---|---|
| `candidate_id`, `round` | string / int | both | Identify the competing design + iteration. |
| `evaluator` | object | both | `type: "human" \| "ai"`; lets the loop treat hand-written and emitted critiques identically. **(synthesized — not in Anthropic's prose)** |
| `verdict` | enum | both | `PASS` \| `NEEDS_WORK` — bare verdict on its own first line, mirroring the shipped evaluator's documented convention. ([github.com/anthropics/cwc-long-running-agents](https://github.com/anthropics/cwc-long-running-agents/blob/main/claude-code-config/.claude/agents/evaluator.md)) |
| `scores.<criterion>` | `{score, rationale}` | both | Four fixed criteria ([anthropic.com](https://www.anthropic.com/engineering/harness-design-long-running-apps)). `rationale` required, especially for low scores, to catch drift/leniency. **The numeric scale is unverified for Anthropic's harness** — 0–5 (or 0–1 / 0–100) follows the general LLM-as-judge convention, where 1-5 / 0-1 / 0-100 are documented scales and pairing scores with explanations improves robustness. ([arxiv.org](https://arxiv.org/html/2411.15594v6)) |
| `overall` | number | both | Reported, but **do not gate on it** — gate per-criterion against thresholds. **(synthesized aggregate; Anthropic gates per-criterion)** |
| `quality_floor` | object of bools | both | Non-negotiables from the frontend-design skill: responsive-to-mobile, visible keyboard focus, reduced-motion respected. Any `false` ⇒ `NEEDS_WORK`. ([github.com/anthropics/claude-code](https://github.com/anthropics/claude-code/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md)) |
| `change_requests[]` | array | both | The actionable payload — each `{criterion, expected, observed, evidence, severity, fix}`. Evidence is a screenshot/diff/code-location ref. `severity` enum is synthesized; the *actionable, evidence-bound* requirement is from primary sources. ([understandingdata.com](https://understandingdata.com/posts/generator-evaluator-harness-design/), [github.com/anthropics/cwc-long-running-agents](https://github.com/anthropics/cwc-long-running-agents/blob/main/claude-code-config/.claude/agents/evaluator.md)) |
| `recommendation` | enum | both | `refine` \| `pivot` \| `accept` — the generator's branch decision (`refine`/`pivot` are Anthropic's terms; `accept` added for the human-loop). ([anthropic.com](https://www.anthropic.com/engineering/harness-design-long-running-apps)) |
| `recommendation_rationale` | string | both | One sentence: scores trending well ⇒ refine; approach not working ⇒ pivot. ([anthropic.com](https://www.anthropic.com/engineering/harness-design-long-running-apps)) |
| `confidence` | enum | both | `high \| medium \| low` — **(unverified): not in any Anthropic source; an LLM-as-judge add-on to flag shaky verdicts.** |

#### Minimal variant (matches Anthropic's shipped harness)

The shipped reference harness keeps the interchange deliberately tiny — the bare verdict on its own first line plus a bulleted findings list that becomes the next builder session's prompt. ([github.com/anthropics/cwc-long-running-agents](https://github.com/anthropics/cwc-long-running-agents/blob/main/claude-code-config/.claude/agents/evaluator.md))

```
NEEDS_WORK
- originality: warm-cream/serif/terracotta is a generic default — pick a brief-specific direction (blocker)
- craft: body text contrast 3.8:1 fails AA, darken --color-body (major)
- floor: keyboard focus ring missing on nav links
recommendation: refine
```

The first line is parsed as the verdict; everything after feeds the next builder session. Upgrade to the full JSON rubric only for subjective/design work — the repo itself ships only the binary pass/fail contract (`test-results.json` defaulting to `{ "feature-1": { "passes": false } }`) and lists the per-criterion rubric (functionality, design, craft, originality with few-shot examples) as a project-specific "going further" upgrade. ([github.com/anthropics/cwc-long-running-agents](https://github.com/anthropics/cwc-long-running-agents))

#### Calibration notes

- Seed the AI evaluator with **few-shot examples that include detailed score breakdowns** — this is how Anthropic aligned the judge to its preferences and reduced score drift, and how it addressed early **leniency** (the evaluator spotting real issues then rationalizing them away). The same exemplars double as the human reviewer's worked examples, keeping both sources on one scale. ([anthropic.com](https://www.anthropic.com/engineering/harness-design-long-running-apps), [understandingdata.com](https://understandingdata.com/posts/generator-evaluator-harness-design/))
- Run the evaluator in a **fresh context with no Write/Edit tools** so it judges only the evidence, not the build narrative. ([github.com/anthropics/cwc-long-running-agents](https://github.com/anthropics/cwc-long-running-agents/blob/main/claude-code-config/.claude/agents/evaluator.md))

#### Open items (unverified)

- The exact per-criterion numeric scale used in Anthropic's production design harness is **(unverified)** — Anthropic states "detailed score breakdowns" and "hard thresholds" but not the scale.
- A `confidence` field, a tie-break rule across competing designs, and a procedure for reconciling multiple human critiques with an AI critique in one loop are **(unverified)** — no primary source specifies them.
- The `LevelEditor.tsx:892` finding example comes from a third-party summary ([understandingdata.com](https://understandingdata.com/posts/generator-evaluator-harness-design/)) and should be treated as illustrative rather than a quoted Anthropic artifact.


---

### G7 — Stop conditions + anti-fixation

**TL;DR.** Do **not** stop on "score reached threshold." Real evaluators plateau *with headroom remaining* and scores are non-monotonic, so a single threshold gate either never fires or fires on a generous score. Use a **bounded loop**: hard iteration cap + budget cap + early-exit on plateau/no-progress, then **select the best-scoring artifact across all iterations** (not the last). Fight local optima with an explicit per-iteration *refine-vs-pivot* decision and, for higher-value runs, a separate metacognitive supervisor agent.

#### Verified iteration-count ranges
- **5–15 iterations per generation** in Anthropic's frontend design harness; full runs stretched **up to ~4 hours**, and the evaluator's scores "improved before plateauing, with headroom still remaining." ([Anthropic](https://www.anthropic.com/engineering/harness-design-long-running-apps), [InfoQ](https://www.infoq.com/news/2026/04/anthropic-three-agent-harness-ai/))
- Research loops cap at **30 iterations** but converge in **~9 steps mean**, with no significant difference in step count across methods — extra iterations rarely help; better *direction* does. ([arXiv 2603.24768](https://arxiv.org/html/2603.24768))
- Practitioner default: **MAX_ITER = 20** with a budget cap (e.g. "all PRs green, or 10 iterations, or $5 spent"). ([explainx](https://explainx.ai/blog/loop-engineering-coding-agents-claude-code-guide-2026))

#### Auto / AI-evaluated mode — stop conditions
Terminate on the **first** of:
1. **Hard iteration cap** (recommend 8–15 for design; 20 absolute ceiling). Anthropic ran 5–15; explainx's sample uses MAX_ITER=20. ([Anthropic](https://www.anthropic.com/engineering/harness-design-long-running-apps), [explainx](https://explainx.ai/blog/loop-engineering-coding-agents-claude-code-guide-2026))
2. **Plateau / no-progress detection.** The coding-loop rule is to stop when "the same error message, empty diff, or failing test appears N times in a row" ([explainx](https://explainx.ai/blog/loop-engineering-coding-agents-claude-code-guide-2026)). Generalizing this to a visual-aesthetic score (stop when the best score is flat for the last K rounds, K≈2–3) is a **reasoned heuristic, not a measured constant (unverified)** — no primary source defines "plateau" for an aesthetic evaluator. Anthropic confirms only that evaluators plateau *with headroom remaining*. ([Anthropic](https://www.anthropic.com/engineering/harness-design-long-running-apps))
3. **Budget cap** (tokens/$/wall-clock). Loop-management cost dominates — "The costliest thing in AI coding is no longer writing code, it's managing the agent loop" — so this is mandatory for unattended runs. ([explainx](https://explainx.ai/blog/loop-engineering-coding-agents-claude-code-guide-2026), [Agent Shortlist](https://agentshortlist.com/articles/loop-engineering))
4. **Per-criterion gate (regression guard).** Score multiple dimensions — Anthropic graded **design quality, originality, craft, functionality** — and give each a **hard minimum**: "each criterion had a hard threshold, and if any one fell below it, the sprint failed," with the generator getting targeted feedback rather than the run "passing" on a strong aggregate. ([InfoQ](https://www.infoq.com/news/2026/04/anthropic-three-agent-harness-ai/), [Anthropic](https://www.anthropic.com/engineering/harness-design-long-running-apps))

> **Selection rule:** because scores are non-monotonic ("Later implementations tended to be better as a whole, but I regularly saw cases where I preferred a middle iteration over the last one"), **keep every iteration's artifact** and pick the best at the end — never assume the final iteration wins. ([Anthropic](https://www.anthropic.com/engineering/harness-design-long-running-apps))

> **Note on the exact numeric thresholds:** Anthropic disclosed the iteration range and that per-criterion hard thresholds exist, but **never published the actual numeric score thresholds or a plateau-detection rule (unverified)** — these must be tuned empirically per project. ([InfoQ](https://www.infoq.com/news/2026/04/anthropic-three-agent-harness-ai/))

#### Human-evaluated mode — stop conditions
- Stop is an **explicit human ship/approval**. The official frontend-design skill deliberately specifies **no numeric scoring or stop threshold** — its stop condition before building is qualitative ("confirmed the relative uniqueness of your design plan"). ([SKILL.md](https://github.com/anthropics/claude-code/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md))
- Still wrap the human loop in a **budget/iteration ceiling** so an un-shipped run can't grind forever, and surface the best-so-far artifact + score trend at each checkpoint. *(Implementation recommendation, not drawn from a specific source — unverified.)*
- Up front, **negotiate a "done" contract**: in Anthropic's full-stack harness the generator proposed what it would build and how success would be verified, and the evaluator reviewed that proposal before any code. ([Anthropic](https://www.anthropic.com/engineering/harness-design-long-running-apps))

#### Anti-fixation tactics (avoid local optima)
1. **Refine-vs-pivot decision after every evaluation.** Instruct the generator to "refine the current direction if scores were trending well, or pivot to an entirely different aesthetic if the approach wasn't working." This is the primary forced-diversification lever, built into Anthropic's harness. ([Anthropic](https://www.anthropic.com/engineering/harness-design-long-running-apps))
2. **Metacognitive self-regulation (SRL).** Feed the agent its **progress trajectory + trend summary** each round and tell it to set goals, plan, monitor progress, and try alternatives. In the study this raised mean design capacity from 72.07 to 106.08 Ah vs. the naive loop. ([arXiv](https://arxiv.org/html/2603.24768))
3. **Co-regulation supervisor (CRDAL).** Add a **separate Metacognitive Co-Regulation Agent** ("like a supervisor or a colleague") that reviews design history and pushes the generator out of ruts. Best results (141.17 vs 72.07 Ah) and **broadest design-space exploration (8,100-cell designs in 20/30 runs vs RWL staying below 6,048) at the same ~9-step cost** — escaping local optima came from *better feedback, not more iterations*. ([arXiv](https://arxiv.org/html/2603.24768), [arXiv abs](https://arxiv.org/abs/2603.24768))
4. **Tried-it memory / forced novelty.** Keep a running note of approaches already attempted so each pass tries something new — built into Anthropic's frontend skill: "Human creators ... always try to do something new, so if you have a space to quickly jot down notes about what you've tried, it can help you in future passes." ([SKILL.md](https://github.com/anthropics/claude-code/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md))
5. **Up-front aesthetic commitment.** Force a color/type/layout/"signature" choice — and a critique against the brief to strip out anything that reads like the generic default — *before* writing code. ([SKILL.md](https://github.com/anthropics/claude-code/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md))
6. **Parallel competing variants > deep single-track iteration.** A design *competition* (distinct aesthetics scored in parallel, winner selected) is itself an anti-fixation mechanism. *(Synthesis/recommendation — no specific source establishes this for visual frontend design; unverified.)*

#### Recommended defaults for this workflow
| Mode | Stop on | Iteration budget | Anti-fixation |
|---|---|---|---|
| Auto (AI/Playwright eval) | plateau (best score flat ≥2–3 rounds, *heuristic*) **or** any per-criterion min missed after cap **or** budget/iteration cap | 8–15 (hard ceiling 20) | refine/pivot each round; tried-it memory; supervisor agent for high-value runs |
| Human eval | explicit human ship | budget/iteration ceiling as safety net | parallel variants + score trend shown at each checkpoint |

In **both** modes: score multiple dimensions, retain all artifacts, and select the best across iterations rather than trusting the last.

---
**Caveats / what could not be verified**
- The "files/git history vs. the context window" framing as the harness's *central principle* is **not supported** by the Anthropic article; what is supported is file-based handoffs, git version control, and context resets with structured handoffs. The "each design iteration starts with fresh context" claim is **unverified**.
- The four-part termination contract was **not** found in full at agentshortlist.com; that source supports only the iteration cap, budget cap, and a verifiable success function. The **no-progress/plateau** element is sourced from explainx, not agentshortlist.
- The "stop after 2–3 non-improving iterations" rule and "parallel variants beat deep iteration" are **reasoned heuristics**, not measured constants in any cited source.
- The Ralph Wiggum metacognition results are in **engineering design (battery packs)**, not frontend UI; the ~2x quality and broader-exploration gains are suggestive but **not yet replicated for visual frontend design (unverified)**.

---

### G8 — Convergence / selection / synthesis

There are two viable models. Pick based on whether you generate **one iteratively-refined design** or **N competing candidates in parallel**.

#### Model A — Iterative convergence (Anthropic's published approach)

Anthropic's frontend harness does **not** run a tournament. It pairs a **generator** with a **separate evaluator** — separating the agent doing the work from the agent judging it is a strong lever, because self-evaluation fails (agents confidently praise their own work). It converges a *single* design direction over **5–15 iterations per generation** (full runs stretching up to ~4 hours; one simplified run logged ~3hr 50min), producing **one final design per run** rather than a bracket of competing designs. ([anthropic.com](https://www.anthropic.com/engineering/harness-design-long-running-apps), [understandingdata.com](https://understandingdata.com/posts/generator-evaluator-harness-design/))

- **Rubric (4 dimensions):** design quality (coherent whole vs collection of parts), originality (custom decisions vs template/library/AI defaults), craft (typography hierarchy, spacing, color harmony, contrast), functionality (usability/task completion). **Weight design + originality higher** — Claude already scores well on craft/functionality, so weighting them lower pushes aesthetic risk-taking. ([anthropic.com](https://www.anthropic.com/engineering/harness-design-long-running-apps), [understandingdata.com](https://understandingdata.com/posts/generator-evaluator-harness-design/))
- **Convergence rule:** each cycle the generator decides to **refine** (scores trending up) or **pivot** to an entirely different aesthetic (approach failing). ([anthropic.com](https://www.anthropic.com/engineering/harness-design-long-running-apps))
- **Don't blindly take the last iteration.** Scores improved overall but the pattern was *not cleanly linear*, and a *middle* iteration was sometimes preferred over the final one — so checkpoint per iteration and allow an earlier one to win. ([anthropic.com](https://www.anthropic.com/engineering/harness-design-long-running-apps))
- **Calibrate the evaluator** with few-shot exemplars first — uncalibrated judges are lenient: they identify legitimate issues, then talk themselves into deciding they're not a big deal. ([understandingdata.com](https://understandingdata.com/posts/generator-evaluator-harness-design/))
- **Drive functionality with the running app:** in the three-agent (planner/generator/evaluator) harness the evaluator navigates live pages and interacts with the interface via **Playwright MCP**, producing detailed critiques rather than surface-level approvals — so functional behavior can be tested on the running product, not just judged visually. ([infoq.com](https://www.infoq.com/news/2026/04/anthropic-three-agent-harness-ai/))

#### Model B — Competing candidates (parallel variants → select a winner)

When you fan out N parallel design variants, use LLM-as-judge selection:

- **Single-output rubric scoring** to screen all N (cheap, linear), then **pairwise/arena judging to break ties** among the top few. Pairwise picks which of two outputs is better rather than scoring each in isolation, and is recommended when relative quality matters more than an absolute score (prompt/model comparisons, A/B selection). ([deepeval.com](https://deepeval.com/guides/guides-llm-as-a-judge))
- A **hybrid of single-output grading for screening and pairwise for tie-breakers** is the practical recommendation. *(The specific "~95% pairwise vs ~90% single-output alignment" figures trace only to a [Medium post](https://medium.com/@jolalf/arena-g-eval-vs-single-output-llm-as-a-judge-case-study-43c86fe0f1c9) and are **(unverified)** — do not ship as fact. The peer-reviewed anchor, MT-Bench, reports a different ~65% GPT-4 order-consistency in a different setting; use the directional claim "pairwise edges pointwise for selection," not the numbers.)*
- **Mitigate position/order bias** — it is severe on open-ended tasks: when answer order is swapped, consistency was ~**65%** for GPT-4 and only ~**23.8%** for Claude-v1; **swap A/B and run both orderings**, and use few-shot exemplars (which raised GPT-4 consistency to ~77.5%). ([medium.com](https://medium.com/@jolalf/arena-g-eval-vs-single-output-llm-as-a-judge-case-study-43c86fe0f1c9))
- **Tournament:** a single-elimination bracket needs **N−1 comparisons** to find the best of N — *(this is a mathematical property of single elimination, not stated in any cited source; treat as background, unverified-from-source.)*

#### Synthesis / grafting (optional)

After a winner is chosen, you can **graft strong ideas from runners-up** via a fan-out/fan-in step: a Claude Code orchestrator breaks down the work, spawns concurrent subagents to produce candidates, and synthesizes their results when workers finish. ([mindstudio.ai](https://www.mindstudio.ai/blog/claude-code-agent-teams-parallel-agents)) *(The recommendation to require clear structured output from each subagent to make the merge reliable is sound practice but is not supported by the cited source — unverified.)* Re-score the synthesized result through the same rubric to confirm it did not regress.

> Caution: grafting risks the "collection of parts" failure the design-quality dimension penalizes. Only graft self-contained elements and re-evaluate coherence afterward. *(This caution is reasoned from the rubric, not a sourced best practice — unverified.)*
>
> Note: "Grafting runner-up ideas onto a winner" is **not** an established named design pattern in any source located; it is inferred from generic fan-out/fan-in synthesis. (unverified)

#### Recording the decision

Persist an **Architecture Decision Record** per selection. ADRs should be **short (a couple of pages)**, capture the **decision, its context, and significant ramifications**, and be written in **lightweight markup such as Markdown** so they can be read and diffed like code. ([martinfowler.com](https://martinfowler.com/bliki/ArchitectureDecisionRecord.html)) An ADR captures a single decision and its rationale along with trade-offs and consequences; the concept was popularized by Michael Nygard's 2011 post. ([adr.github.io](https://adr.github.io/))

- The **MADR** template and the **Y-statement** ("In the context of X, facing Y, we decided for Z to achieve W, accepting downside V") **are sourceable at [adr.github.io](https://adr.github.io/)** — it cites the Y-statement (Zdun et al.) and references MADR. *(V&V salvage: these were previously rejected only because pinned to the wrong URL, martinfowler.com; reinstated with the correct citation.)* The classic **Nygard five-element template (title, status, context, decision, consequences)** is from Nygard's original 2011 post; the exact element list was not on the cited pages, so cite Nygard directly for it.

Recommended fields for a design-selection ADR (practical recommendation, not sourced):
- Winner (candidate/iteration id) + link to artifact/screenshot
- Per-dimension rubric scores for winner and each runner-up
- Selection method (iterative-converge / single-output / pairwise / tournament), judge model, and calibration set
- Any grafted elements and their source candidate
- Human override (if a human picked against the judge) and why
- Date, status (accepted/superseded)

---
**Verification notes for this section:**
- Model A (Anthropic generator/evaluator, 4-dim rubric, 5–15 iterations / ~4h, weighting, calibration/leniency, Playwright MCP, refine-vs-pivot, non-monotonic scores) is **solidly verified** against anthropic.com, understandingdata.com, and infoq.com. Two claims (refine-vs-pivot; non-monotonic / prefer middle iteration) were originally cited to understandingdata.com but are actually supported on the **anthropic.com** page — re-attributed.
- **Rejected:** "pairwise is more consistent than absolute scoring / N−1 comparisons" attributed to confident-ai.com (page does not support it); the single-output "~87–89%" figure (source says ~90%); "structured output makes synthesis reliable" attributed to mindstudio.ai (not in source); Nygard 5-element format + alternatives attributed to adr.github.io; MADR / Y-statement attributed to martinfowler.com.
- The tournament-and-grafting lineage is **extrapolated** from general LLM-as-judge literature; there is no primary Anthropic guidance endorsing N-way tournaments or grafting for design.

---

### G9 — Terminology reconciliation

**Verdict: "design competition" is a drifted, non-standard term.** It does not appear in Anthropic's primary engineering writeup, in the official Claude Code `frontend-design` plugin, or in the cited eval literature. Use it only as informal shorthand and define it on first use. The bleeding-edge (2026) standard vocabulary is below.

#### Canonical vocabulary (Anthropic + community)

| Concept | Standard term | Source of authority |
|---|---|---|
| The overall scaffold around the model | **harness** ("harness design") | [Anthropic, *Harness design for long-running application development*](https://www.anthropic.com/engineering/harness-design-long-running-apps) |
| The two-agent loop where one builds and one critiques | **generator–evaluator loop**, explicitly **GAN-inspired** — "Taking inspiration from Generative Adversarial Networks (GANs), I designed a multi-agent structure with a generator and evaluator agent." | [Anthropic (same article)](https://www.anthropic.com/engineering/harness-design-long-running-apps) |
| The three roles in the full harness | **Planner → Generator → Evaluator** | [Anthropic (same article)](https://www.anthropic.com/engineering/harness-design-long-running-apps) |
| The community packaging of that pattern | **GAN-style harness** (e.g. the `gan-style-harness` Claude Code skill); practitioner writeups also use "Generator-Evaluator Harness" / "GAN-Inspired Architecture" | [gan-style-harness skill](https://github.com/affaan-m/everything-claude-code/blob/main/skills/gan-style-harness/SKILL.md); [practitioner writeup](https://understandingdata.com/posts/generator-evaluator-harness-design/) |
| Using an LLM to score/critique output | **LLM-as-a-Judge** — applied as pointwise (single-output) scoring or pairwise (pick-a-winner) comparison | [Confident AI eval guide](https://www.confident-ai.com/blog/why-llm-as-a-judge-is-the-best-llm-evaluation-method) |
| Generating N candidates and selecting the best | **best-of-N** (a.k.a. candidate sampling + selection) | ML standard term *(general field knowledge; not tied to a specific cited source here)* |
| The model driving the evaluator through a live UI | **Playwright MCP evaluator** — given the Playwright MCP to "interact with the live page directly before scoring each criterion" | [Anthropic (same article)](https://www.anthropic.com/engineering/harness-design-long-running-apps) |

#### Key disambiguation (this is the trap)

Anthropic's *published* frontend pattern is **iterative refinement of a single design** — "I ran 5 to 15 iterations per generation," with the evaluator grading **design quality, originality, craft, and functionality** in the section "Frontend design: making subjective quality gradable" ([Anthropic](https://www.anthropic.com/engineering/harness-design-long-running-apps)). It is *not* a parallel bake-off. Two genuinely different patterns get conflated under "design competition":

- **Generator–evaluator loop** — one design, refined over iterations against a rubric. (Anthropic's actual published approach.)
- **Best-of-N / candidate selection** — N designs generated in parallel, then ranked and a winner picked. The comparative scoring here maps to **pairwise LLM-as-judge**, which "does not output any score, but instead choose a winner out of a list of different LLM outputs," versus **pointwise** single-output scoring ([Confident AI](https://www.confident-ai.com/blog/why-llm-as-a-judge-is-the-best-llm-evaluation-method)).

The official `frontend-design` plugin reinforces the single-track stance: "Work in two passes" (brainstorm a plan, review against the brief, build), "Critique your own work as you build, taking screenshots," and "only show ideas to the user when you have higher confidence it'll delight them" — i.e. fewer high-confidence options, not many parallel ones ([SKILL.md](https://github.com/anthropics/claude-code/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md?plain=1)).

#### Recommendation for this spec

Pick the term that matches the mechanism you actually implement:
- If you refine one design across iterations → call it a **generator–evaluator (GAN-style) harness**.
- If you fan out N competing designs and pick a winner → call it **best-of-N candidate selection** with a **pairwise LLM-as-judge** (or human) evaluator.
- Reserve "design competition" as a plain-English label only, mapped explicitly to one of the above.

#### Drifted / avoid

- **"Design competition"** — not used by Anthropic or the official plugin; ambiguous between iterative refinement and best-of-N. Flag and define on first use.
- **"GAN harness" implying *adversarial training*** — it is only GAN-*inspired* (role separation: a skeptical evaluator vs. a generator). There is no gradient or adversarial training involved. *(The "no gradient/adversarial training" caveat is reasonable inference from the role-based description, not a verbatim source statement — treat as interpretation.)*
- **Don't use "LLM-as-judge" for the whole loop** — it names only the evaluation/scoring component, not the generate-iterate machinery.

#### Unverified / corrected from the source draft

- **(unverified)** The claim that "LLM-as-a-Judge is *the default* method for evaluating LLM applications at scale, with judges agreeing with humans ~85% of the time" could **not** be confirmed — the cited DeepEval guide presents LLM-as-judge as one approach among several and contains no 85% agreement figure. Do not cite a specific agreement percentage in the spec without a verifiable source.
- **(unverified)** The operational specifics for pointwise vs. pairwise ("scales linearly," "drifts between runs," "requires both orderings," "quadratic calls") are **not** stated in the cited Confident AI source. The pointwise-vs-pairwise distinction itself is verified; the cost/reliability quantifiers are not — drop them or source them separately.
- **Correction:** the `gan-style-harness` skill is real, but it is documented in its own repo/plugin listings, **not** in the understandingdata.com writeup (which does not mention it). Attribute each to its correct source.

---

### G10 — Mode bindings (concrete setup)

The competition harness keeps **one generation surface** and swaps the *judge* behind a mode flag. Both modes consume the same generator output (the `frontend-design` plugin skill) and feed critique back through a shared file the generator reads on its next pass. This mirrors Anthropic's generator-evaluator pattern, where separating the agent doing the work from the agent judging it "proves to be a strong lever." ([Anthropic][1])

#### Shared generation surface (both modes)
- **Generator** = the official `frontend-design` plugin (`plugins/frontend-design/skills/frontend-design/SKILL.md`, by Prithvi Rajasekaran and Alexander Bricken). It emits a compact design-token system (4–6 named hex values, type/layout, a "signature" element) and works in two passes — brainstorm a design plan, then review it against the brief before building — recommending screenshots for self-review ("a picture is worth 1000 tokens"). It does **not** mention Playwright or define an evaluator/competition loop — those are added by the harness. ([Anthropic GitHub][2], [Anthropic GitHub][6])
- **Variant fan-out (optional)** = git worktrees. Spawn N isolated variants under `.worktrees/` (`./scripts/spawn-parallel.sh <name> 3`), one branch/Claude per worktree in its own terminal, exploiting LLM non-determinism as "N valid solutions to choose from." ([parallel-worktrees][3]) Note: per-variant dev-server **ports are not auto-assigned** by the skill — handle manually for side-by-side. ([parallel-worktrees][3])

> Composition note (unverified framing): Anthropic's writeup describes a **sequential** single-generator loop (one variant refined over 5–15 iterations), not N parallel competing worktrees judged once. The "competition" framing here is a community composition layered on top of Anthropic's loop — decide which you actually want for the spec.

#### Mode A — Auto / Playwright (AI evaluator)
The evaluator is a **fresh-context subagent with no Write/Edit tools**, defined at `agents/evaluator.md` and invoked headless:
```bash
claude --agent evaluator -p "Review the most recent commit against its spec."  # -> PASS | NEEDS_WORK + findings
```
([Anthropic GitHub][4])
- **Tooling:** in Anthropic's frontend-design runs the evaluator was given the **Playwright MCP**, which let it interact with the live page directly before scoring each criterion and writing a critique; in full-stack mode it clicked through the running app like a user, testing UI features, API endpoints, and database states. ([Anthropic][1]) Caveat: Playwright-in-evaluator appears in the companion repo only under "Going further" as a *browser-verified evaluator* you build yourself (add `@playwright/mcp` or Claude in Chrome to `tools:` in `agents/evaluator.md`) — **it is not shipped** in `cwc-long-running-agents`. ([Anthropic GitHub][4])
- **Rubric:** four criteria — **design quality, originality, craft, functionality** — with design quality and originality emphasized over craft and functionality; in full-stack mode each criterion has a hard threshold and any one falling below it fails the sprint. Calibrate with few-shot examples and detailed score breakdowns to reduce drift. ([Anthropic][1]) *(The exact weights and few-shot calibration examples are project-specific and not published — author locally. The often-cited rationale that the weighting exists "to penalize AI slop" is **unverified** in the source text.)*
- **Loop:** 5–15 iterations/generation; after each score the generator refines (scores trending well) or pivots to a different aesthetic (approach not working). ([Anthropic][1]) The repo's canonical loop is a bash `while` loop alternating `claude -p` (generator) and `claude --agent evaluator`, writing non-PASS verdicts to `NEXT_FINDINGS.md`. ([Anthropic GitHub][4])
- **Gating plumbing (from `cwc-long-running-agents`):** a default-FAIL `test-results.json`; a `PreToolUse` hook denies any write to the results file unless the agent first `Read` its evidence (screenshots/console logs/result files matching `track-read.sh`) (unverified: the exact gate-hook filename `verify-gate.sh`); operator hooks `kill-switch.sh` (halts on an `AGENT_STOP` file), `steer.sh` (surfaces `STEER.md` once, then clears it), and `commit-on-stop.sh`. ([Anthropic GitHub][4])

#### Mode B — Human (side-by-side review)
Swap the evaluator subagent for a person at the same loop boundary.
- **Review surface:** run each worktree's dev server and compare visually; for code, compare with `git diff main` per worktree, then `git merge <variant>` the winner and `cleanup-worktrees.sh` (unverified: a `sync-worktrees.sh --interactive` review command). ([parallel-worktrees][3]) Mid-2026 practitioner guidance puts teams at 4–8 concurrent worktrees per developer, with **review — not Claude — as the bottleneck** above that. ([Claude Directory][5])
- **Critique-capture form:** Anthropic ships no standard form — its documented human role lives at the *tuning* stage (read evaluator logs, note divergences from your own judgment, update the QA prompt over several rounds). ([Anthropic][1]) For a competition loop, standardize a `FINDINGS.md` (the same slot the AI evaluator writes) that the generator reads next — suggested schema: `variant | verdict (keep/refine/kill) | per-criterion note (design/originality/craft/functionality) | concrete fix`. *(This schema is a local design recommendation, not from any source.)* This keeps Mode A and Mode B drop-in interchangeable.

#### Wiring summary
| | Auto / Playwright | Human |
|---|---|---|
| Judge | `agents/evaluator.md` subagent (no Write/Edit tools) ([4]) | reviewer |
| Tooling | Playwright MCP on live dev server (you wire it in — not shipped) ([1],[4]) | dev servers per worktree, `git diff main`, merge/cleanup scripts ([3]) |
| Scoring | 4-criterion rubric, design/originality emphasized, few-shot calibrated ([1]) | `FINDINGS.md` form (local convention, mirrors rubric) |
| Feedback file | `NEXT_FINDINGS.md` → generator ([4]) | `FINDINGS.md` → generator (local convention) |
| Loop control | bash while-loop + PreToolUse read-gate + control hooks ([4]) | merge winner, cleanup ([3]) |

Recommended companion stack (community): TypeScript LSP, Frontend Design, Chrome DevTools, Playwright, GitHub, Vercel. ([Composio][7]) *(Composio recommends this combined stack but does not specify the multi-screen-size screenshot-comparison workflow sometimes attributed to it — treat that workflow detail as unverified.)*

[1]: https://www.anthropic.com/engineering/harness-design-long-running-apps
[2]: https://raw.githubusercontent.com/anthropics/claude-code/main/plugins/frontend-design/skills/frontend-design/SKILL.md
[3]: https://github.com/spillwavesolutions/parallel-worktrees
[4]: https://github.com/anthropics/cwc-long-running-agents
[5]: https://www.claudedirectory.org/blog/claude-code-worktrees-guide
[6]: https://github.com/anthropics/claude-code/tree/main/plugins/frontend-design
[7]: https://composio.dev/content/top-claude-code-plugins

---

## Rejected claims

Claims the verifier removed (hallucinated/unverifiable sources, overstated specifics, or vendor marketing). 33 total.

- **G1 — DESIGN.md + token-file schema for AI frontend agents** — DTCG tokens require both $value AND $type (claim 8 stated '$value and $type' as required).
  - _Rejected:_ Overstated. The DTCG 2025.10 spec states only $value is required ('An object with a $value property is a token'); $type is explicitly optional ('A token's type can be specified by the optional $type property'). Corrected in the verified claim.
- **G1 — DESIGN.md + token-file schema for AI frontend agents** — The detailed DTCG $-key schema and composite types are documented at the W3C announcement URL (the source_url originally cited for claim 8).
  - _Rejected:_ Source mismatch. The cited announcement page (w3.org/.../2025/10/28/...) supports only the release date and the existence of aliasing/inheritance — it does NOT contain the $value/$type/$description/$extensions/$deprecated schema or the shadow/gradient/border/typography composite types. Those specifics are confirmed only at the actual spec, designtokens.org/tr/2025.10/format/, which is now cited instead.
- **G1 — DESIGN.md + token-file schema for AI frontend agents** — Meta's Astryx (June 2026) gives agents a readable design system; its schema relative to DTCG is known.
  - _Rejected:_ Unverified — listed only as an open question in the finding; the cited techtimes article was 403-blocked and no primary source confirms its schema. Marked unverified in the section, not asserted.
- **G2 — Brief / intent schema: the minimum-viable structured brief for prompting AI frontend generation with aesthetic direction that reliably steers away from generic "AI slop."** — The claude.com Skills blog lists 'three-card feature grids' as a convergent default to reject.
  - _Rejected:_ Not present in the source. The blog's list of convergent defaults is 'Inter fonts, purple gradients on white backgrounds, and minimal animations' — it does not mention card grids. Card-grid avoidance ('generic SaaS card grid') is supported only by the OpenAI GPT-5.4 blog, not by the Anthropic Skills blog. Misattribution corrected in the final section.
- **G2 — Brief / intent schema: the minimum-viable structured brief for prompting AI frontend generation with aesthetic direction that reliably steers away from generic "AI slop."** — The Skills blog presents 'three strategies' (guide design dimensions, reference inspirations non-prescriptively, name convergent defaults to reject).
  - _Rejected:_ The source does not enumerate a canonical 'three strategies.' It presents 'right altitude' guidance plus four design dimensions (Typography, Color & Theme, Motion, Backgrounds), inspiration sourcing, and a font-avoid list. The substance is supported; the specific count 'three strategies' is not in the source and is dropped.
- **G2 — Brief / intent schema: the minimum-viable structured brief for prompting AI frontend generation with aesthetic direction that reliably steers away from generic "AI slop."** — The avoid-list font line 'Inter, Roboto, Arial, system stacks' is sourced to the claude.com Skills blog.
  - _Rejected:_ Arial is not in the Skills blog list, which is 'Inter, Roboto, Open Sans, Lato, default system fonts.' Arial appears in the OpenAI GPT-5.4 list. Corrected to cite each font set to its actual source.
- **G2 — Brief / intent schema: the minimum-viable structured brief for prompting AI frontend generation with aesthetic direction that reliably steers away from generic "AI slop."** — The signature is 'the single unique element this page will be remembered by that embodies the brief' (verbatim quote with the 'that embodies the brief' clause), and the self-critique quote 'reads like the generic default you would produce for any similar page rather than a choice made for this specific brief' (verbatim).
  - _Rejected:_ The core meaning is verified, but these exact verbatim strings could not be confirmed from the fetched SKILL.md (the signature quote confirmed only through 'the single unique element this page will be remembered by'; the self-critique was paraphrased in the source as confirming specificity vs. a recycled default). The verbatim extensions are marked unverified rather than presented as quotes.
- **G3 — Parallelism: how many competing frontend design candidates to generate, how to enforce diversity, how to present them side-by-side, and the tradeoffs of git worktrees vs parallel subagents vs Stitch .variants() (plus concurrency limits).** — The frontend-design SKILL contains a four-question framework (purpose, tone/audience, constraints, differentiation) and a ~12-item aesthetic 'tone' taxonomy (brutally minimal, maximalist chaos, retro-futuristic, organic, luxury, playful, editorial, brutalist, art deco, soft pastel, industrial) to assign one tone per candidate.
  - _Rejected:_ Fabricated specifics. The SKILL.md has no such tone taxonomy and no purpose/tone/constraints/differentiation framework. It uses a 3-part grounding (name a concrete subject, its audience, the page's single job) and lists 'maximalist / minimal / brutalist / editorial' only incidentally — three of those appear as AI-generated defaults to AVOID, not as a diversity menu. The list of 12 tones and the four-question framing do not appear in the source. This is the load-bearing diversity lever in the proposed section, so its rejection undercuts the 'assign each candidate a distinct SKILL tone' recommendation.
- **G3 — Parallelism: how many competing frontend design candidates to generate, how to enforce diversity, how to present them side-by-side, and the tradeoffs of git worktrees vs parallel subagents vs Stitch .variants() (plus concurrency limits).** — Claude Code's workflow engine caps concurrent agent() calls at min(16, cpu_cores - 2) — hard ceiling 16, effective limit set by CPU cores, not user-configurable.
  - _Rejected:_ Not supported by the cited mindstudio.ai page, which only says you can 'configure limits through Claude Code's settings' and gives no formula, no 16-cap, and no cpu_cores-2 expression. The precise min(16, cpu_cores-2) figure could not be confirmed in any source; treat as unverified.
- **G3 — Parallelism: how many competing frontend design candidates to generate, how to enforce diversity, how to present them side-by-side, and the tradeoffs of git worktrees vs parallel subagents vs Stitch .variants() (plus concurrency limits).** — Best-of-N parallel sampling quality saturates by N≈4 with diminishing returns; parallel generation is O(1) wall-clock vs O(N) sequential; sequential gives slightly higher diversity.
  - _Rejected:_ Source mismatch. arxiv 2507.08944 is 'Optimizing Sequential Multi-Step Tasks with Parallel LLM Agents' (M1-Parallel), which is about running multi-agent teams in parallel for up to ~2.2x speedup; it does NOT establish an N≈4 best-of-N quality-saturation point, O(1)-vs-O(N) framing, or a sequential-diversity edge. The N≈4 saturation figure — a primary justification for the '3–5 candidates' default — is unverified.
- **G3 — Parallelism: how many competing frontend design candidates to generate, how to enforce diversity, how to present them side-by-side, and the tradeoffs of git worktrees vs parallel subagents vs Stitch .variants() (plus concurrency limits).** — Raw idea diversity plateaus around 20–30 candidates while critic/feedback diversity saturates at ≈3 critics.
  - _Rejected:_ Not present in the cited source (arxiv 2602.20408 abstract supports the general 'must engineer diversity' point but states neither the 20–30 plateau nor the ≈3-critic saturation number). Both numbers are unverified; the '≈3 critics' figure is cited in the proposed section as independent support for the 3–5 sweet spot and should not be relied on.
- **G3 — Parallelism: how many competing frontend design candidates to generate, how to enforce diversity, how to present them side-by-side, and the tradeoffs of git worktrees vs parallel subagents vs Stitch .variants() (plus concurrency limits).** — Playwright's HTML reporter shows candidate images side by side, providing a standard contact-sheet review surface.
  - _Rejected:_ Not supported by the cited URL (playwright.dev/docs/screenshots), which documents screenshot capture only and makes no mention of an HTML reporter rendering images side by side. The screenshot primitives are real; the 'reporter shows images side by side' sub-claim is unverified at this source.
- **G4 — Evaluator protocols (Playwright + human)** — The design-review protocol runs 'seven phases.'
  - _Rejected:_ The source actually defines eight phases (Phase 0 Preparation through Phase 7 Content & Console). The phase names listed in the finding are all correct, but the count 'seven' is wrong — it is eight. Corrected in the final section.
- **G5 — Rubric: weights + AI-slop checklist + few-shot. A concrete evaluator rubric for frontend design with criterion weights (design quality, originality, craft, functionality), an actionable AI-slop anti-pattern checklist, and a few-shot calibration format that is both human-readable and machine-scorable.** — The 0.35 / 0.35 / 0.20 / 0.10 criterion weights, the 0–10 integer scale and 0–100 weighted aggregation.
  - _Rejected:_ Not published by Anthropic. The post explicitly gives only the weighting DIRECTION (design quality + originality above craft + functionality) and states it does not publish numbers. These specific weights and scale are an unverified recommendation and must be labeled as such, not presented as sourced.
- **G5 — Rubric: weights + AI-slop checklist + few-shot. A concrete evaluator rubric for frontend design with criterion weights (design quality, originality, craft, functionality), an actionable AI-slop anti-pattern checklist, and a few-shot calibration format that is both human-readable and machine-scorable.** — The gating rule 'any criterion < 4 caps the aggregate at 49', and verdict thresholds (>=80 ship / 50–79 iterate / <50 reject).
  - _Rejected:_ No source. Whether Anthropic uses hard gating vs pure weighted average is unconfirmed; these thresholds are invented and must be marked (unverified).
- **G5 — Rubric: weights + AI-slop checklist + few-shot. A concrete evaluator rubric for frontend design with criterion weights (design quality, originality, craft, functionality), an actionable AI-slop anti-pattern checklist, and a few-shot calibration format that is both human-readable and machine-scorable.** — The machine-scorable evaluator JSON output schema and the specific few-shot anchor records (anchor-reject-01 with scores 4/2/7/8, weighted_total 38, etc.).
  - _Rejected:_ Anthropic has not published the evaluator's structured-output schema or any actual few-shot example text/scores. These are fabricated illustrations; legitimate as a 'recommended implementation' but must not be attributed to Anthropic.
- **G6 — Critique interchange schema: the canonical critique/feedback record that both a human reviewer can fill by hand and an AI evaluator can emit in a design-competition loop (per-criterion score, rationale, concrete change requests, refine-vs-pivot recommendation).** — Anthropic publishes a single literal JSON critique schema for the design evaluator (the canonical record).
  - _Rejected:_ No source contains a published JSON schema for the design evaluator. The four-criterion rubric and refine/pivot field are described in prose; the JSON record in the proposed section is an explicit synthesis, not a copied Anthropic artifact. The finding itself flags this in its open questions, so it is not asserted as fact — but any wording implying Anthropic shipped the JSON is rejected.
- **G6 — Critique interchange schema: the canonical critique/feedback record that both a human reviewer can fill by hand and an AI evaluator can emit in a design-competition loop (per-criterion score, rationale, concrete change requests, refine-vs-pivot recommendation).** — Per-criterion scoring uses a specific numeric scale (e.g. 0–5) in Anthropic's production design harness.
  - _Rejected:_ Anthropic mentions 'detailed score breakdowns' and 'hard thresholds' but never states the numeric scale. 0–5 / 0–1 / 0–100 come from the general LLM-as-judge survey, not from the Anthropic design harness. Must be marked as a convention, not Anthropic's documented scale.
- **G6 — Critique interchange schema: the canonical critique/feedback record that both a human reviewer can fill by hand and an AI evaluator can emit in a design-competition loop (per-criterion score, rationale, concrete change requests, refine-vs-pivot recommendation).** — The interchange record includes a confidence field, a tie-break rule across competing designs, or a rule for reconciling multiple human critiques with an AI critique.
  - _Rejected:_ No primary source specifies any of these. They are reasonable design additions but unverified; the confidence field is correctly labeled in the proposed section as 'not in Anthropic's prose.'
- **G7 — Stop conditions + anti-fixation for AI design iteration loops (auto/scored vs. human-ship modes), tactics to escape local optima, and verified iteration-count ranges.** — The harness's CENTRAL PRINCIPLE is that progress lives in files and git history, not the model's context window, and each iteration starts with fresh context.
  - _Rejected:_ Overstated framing. The article describes file-based handoffs, git version control, and context resets with structured handoffs as solutions to context limitations, but it does not frame 'progress lives in files/git, not the context window' as the central principle, nor state that each iteration of the design loop starts with fresh context. The substantive mechanisms (verified separately) are real; the 'central principle / not the context window' wording is not supported.
- **G7 — Stop conditions + anti-fixation for AI design iteration loops (auto/scored vs. human-ship modes), tactics to escape local optima, and verified iteration-count ranges.** — agentshortlist.com converges on a FOUR-part termination contract that includes no-progress detection halting when N passes produce no measurable change.
  - _Rejected:_ Overstated. The agentshortlist article supports only three of the four parts — max iteration cap, token/dollar budget cap, and a verifiable success function. It does not describe no-progress / plateau detection. The no-progress element is supported by explainx, not by this source, so attributing a four-part contract (including no-progress) to agentshortlist is unsupported.
- **G8 — Convergence / selection / synthesis: how to pick the winning design among competing frontend candidates, whether/how to synthesize, and how to record the decision.** — Pairwise comparison typically achieves higher consistency than absolute scoring because relative comparison is easier to reach consensus on; a single-elimination tournament needs only N-1 comparisons to find the best of N responses. (cited confident-ai.com)
  - _Rejected:_ The cited confident-ai.com page does not state that pairwise is more consistent than absolute scoring, and never mentions single-elimination tournaments or N-1 comparisons. The fetched page presents pairwise and single-output as different tools with similar (~85%) human alignment. N-1 is a trivially true property of single-elimination but is not in the source — unsupported as a sourced claim.
- **G8 — Convergence / selection / synthesis: how to pick the winning design among competing frontend candidates, whether/how to synthesize, and how to record the decision.** — Single-output scoring reaches ~87-89% human alignment. (cited medium jolalf)
  - _Rejected:_ Overstated specific. The article reports single-output alignment 'up to ~90%' (and 65%-77.5% in other settings), not 87-89%. The 87-89% figure does not appear in the source.
- **G8 — Convergence / selection / synthesis: how to pick the winning design among competing frontend candidates, whether/how to synthesize, and how to record the decision.** — Clear structured output formats from sub-agents make the synthesis step reliable. (cited mindstudio.ai)
  - _Rejected:_ The mindstudio page describes fan-out/fan-in orchestration and synthesis via a shared task list, but does not claim structured output formats are what make synthesis reliable. This specific assertion is not in the source.
- **G8 — Convergence / selection / synthesis: how to pick the winning design among competing frontend candidates, whether/how to synthesize, and how to record the decision.** — adr.github.io documents the Nygard format as title, status, context, decision, consequences and says to explicitly list alternatives considered with pros and cons.
  - _Rejected:_ The fetched adr.github.io homepage references Nygard but does not enumerate the five-element format or instruct listing alternatives with pros/cons. The five-element enumeration is widely accepted from Nygard's original 2011 post but is not supported by the cited URL.
- **G8 — Convergence / selection / synthesis: how to pick the winning design among competing frontend candidates, whether/how to synthesize, and how to record the decision.** — MADR and the Y-statement ('In the context of X, facing Y, we decided for Z to achieve W, accepting downside V') are accepted minimal templates. (cited martinfowler.com)
  - _Rejected:_ The martinfowler.com ADR page does not mention MADR or the Y-statement template. These are real artifacts elsewhere, but the cited source does not support them.
- **G9 — Terminology reconciliation: whether "design competition" is the standard term, or whether generator-evaluator / GAN-style harness / best-of-N / LLM-as-judge is the preferred bleeding-edge vocabulary (Anthropic + community, 2026).** — 'LLM-as-a-Judge' is described in 2026 as the default method for evaluating LLM applications at scale, with LLM judges agreeing with human reviewers ~85% of the time.
  - _Rejected:_ The cited DeepEval page (https://deepeval.com/guides/guides-llm-as-a-judge) does NOT describe LLM-as-a-Judge as 'the default/standard method' (it presents it as one approach among several) and contains NO '~85% agreement with humans' figure. The specific 85% number is unsupported by the source — treated as a hallucinated/overstated specific.
- **G9 — Terminology reconciliation: whether "design competition" is the standard term, or whether generator-evaluator / GAN-style harness / best-of-N / LLM-as-judge is the preferred bleeding-edge vocabulary (Anthropic + community, 2026).** — Pointwise scoring 'scales linearly but drifts between runs' while pairwise comparison is 'more reliable but requires both orderings and quadratic calls'.
  - _Rejected:_ The cited confident-ai page confirms the pointwise-vs-pairwise distinction and that pairwise picks a 'winner', but it does NOT state the operational specifics: linear scaling, drift between runs, requiring both orderings, or quadratic call counts. These specifics are overstated beyond what the source supports.
- **G9 — Terminology reconciliation: whether "design competition" is the standard term, or whether generator-evaluator / GAN-style harness / best-of-N / LLM-as-judge is the preferred bleeding-edge vocabulary (Anthropic + community, 2026).** — The understandingdata.com writeup codifies the pattern under the name 'gan-style-harness'.
  - _Rejected:_ Source mismatch: the understandingdata.com page does not mention 'gan-style-harness' at all. That skill name is verified, but only via its own GitHub/plugin-hub listings, not via this practitioner writeup. The two claims were incorrectly attributed to a single source.
- **G10 — Mode bindings (concrete setup): the exact wiring for Auto/Playwright evaluation (evaluator agent + MCP/tooling) versus Human review (side-by-side surface + critique capture), grounded in real 2026 tools.** — The four criteria are weighted to penalize generic 'AI slop' patterns.
  - _Rejected:_ The article confirms design quality and originality are emphasized over craft and functionality, but the specific rationale 'to penalize generic AI slop' is not present in the verified article text. Kept the weighting fact; dropped the unverified rationale.
- **G10 — Mode bindings (concrete setup): the exact wiring for Auto/Playwright evaluation (evaluator agent + MCP/tooling) versus Human review (side-by-side surface + critique capture), grounded in real 2026 tools.** — Review is done via `sync-worktrees.sh --interactive`.
  - _Rejected:_ The parallel-worktrees source confirms review via `git diff main`, merge, and cleanup-worktrees.sh, but did not confirm a `sync-worktrees.sh --interactive` command. Treating the specific command name as unverified.
- **G10 — Mode bindings (concrete setup): the exact wiring for Auto/Playwright evaluation (evaluator agent + MCP/tooling) versus Human review (side-by-side surface + critique capture), grounded in real 2026 tools.** — Composio recommends pairing Frontend Design with Playwright + Chrome DevTools MCP to compare against target screenshots at multiple screen sizes and iterate.
  - _Rejected:_ The page recommends the combined stack (Frontend Design + Chrome DevTools + Playwright) but does NOT describe the specific workflow of comparing against target screenshots at multiple screen sizes and iterating. That workflow specificity is overstated; kept only the stack recommendation.
- **G10 — Mode bindings (concrete setup): the exact wiring for Auto/Playwright evaluation (evaluator agent + MCP/tooling) versus Human review (side-by-side surface + critique capture), grounded in real 2026 tools.** — verify-gate.sh is the named PreToolUse gate hook.
  - _Rejected:_ The repo confirms track-read.sh and a PreToolUse hook that denies writes to the results file, but the fetch did not independently confirm the exact filename 'verify-gate.sh'. The gating mechanism is verified; the specific second filename is treated as unverified.
