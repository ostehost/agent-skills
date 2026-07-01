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
- **Optional/contextual:** Playwright/MCP (for Auto mode), ImageMagick `montage` (for contact sheets), and `ajv` (for strict JSON schema validation).

## Quick Start
1. Provide a `DESIGN.md` and `BRIEF.yaml` in the project root to define the L0/L1 intent.
2. Execute `run-harness.sh` to trigger the evaluation loop.
