# AGENTS.md

Public shared skills for agent workflows. Canonical catalog lives here; do not
edit generated/vendor copies in downstream repos — update here, then sync.

## Commands

- `scripts/validate-skills` — skill frontmatter + `skills.sh.json` shape gate
- `scripts/run-checks` — local mirror of `.github/workflows/validate.yml`
- `scripts/install-skills` — list/install skills into an agent skills directory
- Dev deps for validation: `python3 -m pip install -r requirements-dev.txt`
  (PyYAML). Prefer an interpreter outside this tree when running autoreview
  isolation self-tests (see `scripts/run-checks` header).

No root `justfile` and no fleet local-eight recipe names. That is intentional:
this repo is an upstream-facing skills fork; inventing a just facade creates
merge friction without a consumer here. Do not claim Universal 8 or local-eight
conformance, and do not invent a root `verify`.

## Rules

- Canonical shared skills live under `skills/<name>/SKILL.md`.
- Keep repo-specific workflows out unless they are useful as public examples.
- Keep secrets, private hostnames, private account IDs, and private URLs out.
- Skill descriptions: short trigger phrase, not full documentation.
- Skill bodies: operational, terse, current.
- Frontmatter: `name` and `description` are required (validated). `user-invocable`
  is the one other field in use here (design-competition) — a host-read flag for
  direct/slash invocation, not something this repo's own tooling checks. Don't
  add other one-off frontmatter fields without a real consumer; nothing enforces
  they stay current otherwise.
- Helper scripts belong under `skills/<name>/scripts/`.
- `skills/<name>/agents/openai.yaml` (behavior-validator, session-viewer) is a
  host-read agent config for OpenAI-compatible hosts; repo tooling does not
  validate it.
- After skill or catalog edits, run `scripts/validate-skills`; use
  `scripts/run-checks` before claiming CI parity.

## Architecture

- Helper scripts are directly runnable: no package manager, bundler, or build
  step. They run straight from the language runtime (`python3`, `node`; `.ts`
  via Node type-stripping). Repository validation uses the small Python
  dependency set in `requirements-dev.txt`.
- A skill may be a single self-contained script (`autoreview`,
  `agent-transcript`) or a small module tree
  (`session-viewer/scripts/{core,importers}`). Both are fine; reach for modules
  only when a skill genuinely outgrows one file.
- `scripts/validate-skills` is the single source of truth for "is this repo
  well-formed". It enforces: per-skill frontmatter with non-empty `name`/
  `description`, `name` matching the skill directory, and a `skills.sh.json`
  that is valid JSON referencing only existing skills (each in at most one
  grouping). Any malformed shape must yield a readable error, never a crash.

## Layout

See README.md's "Included Skills" list for the current skill inventory —
kept there as the single copy so this section can't drift out of sync with it
again.

## Safety

- Preserve pre-existing dirty/unrelated work; stage only owned paths.
- Do not commit, push, tag, or publish without explicit authorization.
- Product depth stays in README/VISION/`docs/`; keep this file operational.
