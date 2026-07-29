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
