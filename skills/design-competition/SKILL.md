---
name: design-competition
description: "Run frontend design generator/evaluator harnesses with human or Playwright review."
user-invocable: true
---

# Design Competition Harness

A frontend **generator–evaluator (GAN-style) harness** that generates a design, scores it against a rubric, feeds critique back, and iterates until it converges — runnable in two **interchangeable** modes: **Human** (a person judges) and **Auto/Playwright** (an AI evaluator judges a live page).

See the included `README.md` and `WORKFLOW.md` for detailed rules on how to run this harness.

## Dependencies

- **Required:** `jq`, `claude`, `git`
- **Optional/contextual:** the `playwright` + `axe-core` npm libraries in the target project (shared capture + machine floor keys, **both** modes), Playwright MCP (Auto-mode evaluator), ImageMagick `montage` (contact sheets), and `ajv` (strict JSON schema validation).

## Quick Start
1. Provide a `DESIGN.md` and `BRIEF.yaml` in the target project root to define the L0/L1 intent
   (plus `tokens/primitives.tokens.json` for the frozen substrate).
2. Check the preconditions: the target project is a git repo with **at least one commit**. The
   harness serves each round's build itself (via the `runs/<id>/live` symlink) unless something is
   already listening on `http://localhost:$PORT` (default 4173) — a pre-existing server must serve
   the current round's build.
3. Run the loop from anywhere:
   `GENERATOR_MODEL=<model-id> MODE=auto PROJECT=/path/to/project scripts/run-harness.sh` (or `MODE=human`).
   `GENERATOR_MODEL` is always required (M1 model-id locking — the shipped agent files carry
   placeholders the wrapper materializes per run); Auto mode also requires `EVALUATOR_MODEL`
   (multimodal, different model family). The chosen ids are recorded in `runs/<id>/RUN_MANIFEST.json`.
   The script itself installs this skill's subagents (`.claude/agents/{generator,evaluator,supervisor}.md`)
   into the target project's `.claude/agents/` and, in Auto mode, copies the pinned Playwright MCP
   config (`templates/mcp.json`) into each round dir — no manual agent or MCP setup.
   In Human mode it renders a blank `REVIEW-SHEET.md` into the round dir and blocks until you save
   the filled sheet as `REVIEW-SHEET.filled.md` (touch `runs/<id>/AGENT_STOP` to halt).

## Tuning what the evaluator rewards and penalizes

The rubric is **not** edited here. `schemas/critique.schema.json` is closed
(`additionalProperties:false`) over exactly four score keys, so a criterion that is only
described in prose can never be emitted, gated, or fed back. Put each kind of tuning where the
loop actually reads it:

| You want to… | Edit | Read by |
| --- | --- | --- |
| Constrain audience, tone, and vocabulary (e.g. ban vendor jargon, demand plain-spoken copy) | `BRIEF.yaml` → `intent.audience` / `intent.tone`, per target project | generator, every pass |
| Penalize a recurring visual or copy cliché | `BRIEF.yaml` → `aesthetic.avoid[]` (`human_cue` + `auto_heuristic`), or a `slop_flags` entry in `rubric.json` | both evaluator seats |
| Pin spacing, line-height, or opacity values | `tokens/primitives.tokens.json` — the frozen substrate; hardcoding px in the rubric bypasses token conformance, which `craft` scores | generator + `craft` |
| Change criteria, weights, or thresholds | `rubric.json` (machine) **and** `rubric.md` (human) together — the weight direction `design_quality + originality > craft + functionality` is asserted by C6 and by L7 precondition P2 |  evaluator, gate |

Viewport coverage is already structural, not advisory: 1440/768/375 are pinned in
`capture-shots.sh` and in the schema enum (proved by C5), and `responsive_1440` / `responsive_768`
/ `responsive_375` / `visible_keyboard_focus` / `contrast_AA_4_5` are gated quality-floor keys —
any false forces `NEEDS_WORK`. The standard targeted throughout is **WCAG 2.2 AA**; do not mix in
thresholds from other design systems without recording which standard they come from.

## Proving the contracts still connect

From the skill root, `scripts/check-conformance.sh` (no arguments) verifies C1–C8: seat-blind
schema, byte-identical human/auto critiques, schema validation, single baton read path, pinned
viewports, rubric weight direction, a startable auto seat, and wired runnable preconditions. Run
it after changing any script, schema, or rubric file — it checks the harness's own contracts, not
a generated round's output.
