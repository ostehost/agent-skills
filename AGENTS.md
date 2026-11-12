# AGENTS.md

Public shared skills for agent workflows. Canonical catalog lives here; do not
edit generated/vendor copies in downstream repos — update here, then sync.

## Commands

- `scripts/validate-skills` — skill frontmatter + `skills.sh.json` shape gate
- `scripts/check-skills` — upstream's gate (CI: `.github/workflows/validate.yml`)
- `scripts/check-fork` — fork-only gate: `fork-tests/`, diataxis,
  `beam-handoff.test.mjs`, design-competition suites, a test-file manifest, and
  an executable-bit check on shebang scripts
  (CI: `.github/workflows/fork-validate.yml`)
- `scripts/run-checks` — runs `check-skills`, then `check-fork`
- `scripts/install-skills` — list/install skills into an agent skills directory
- Dev deps: `python -m pip install -r requirements-dev.txt` (PyYAML, Pillow)
  into an interpreter outside this tree, plus `npm ci --ignore-scripts` for the
  typecheck. `scripts/run-checks` refuses an in-tree interpreter, one missing
  PyYAML or Pillow, or a `TMPDIR` inside shared scratch.

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
- Autoreview consumers use one shared installation and a Markdown entrypoint. Do not restore vendored autoreview implementations or tests.

## Architecture

- Helper scripts are directly runnable: no bundler or build step, and installed
  skills need no `npm install`. They run straight from the language runtime
  (`python3`, `node`; `.ts` via Node type-stripping). Development needs the
  Python set in `requirements-dev.txt` and `npm ci --ignore-scripts` for the
  session-viewer typecheck.
- A skill may be a single self-contained script (`autoreview`,
  `agent-transcript`) or a small module tree
  (`session-viewer/scripts/{core,importers}`). Both are fine; reach for modules
  only when a skill genuinely outgrows one file.
- `scripts/validate-skills` is the single source of truth for "is this repo
  well-formed". It enforces: per-skill frontmatter with non-empty `name`/
  `description`, `name` matching the skill directory, and a `skills.sh.json`
  that is valid JSON referencing only existing skills (each in at most one
  grouping). Any malformed shape must yield a readable error, never a crash.
- Keep `scripts/check-skills`, `scripts/check-skills.test.py`, and
  `.github/workflows/validate.yml` byte-identical to upstream, except one fork
  line in `validate.yml`: the `macos-sandbox` repository guard (see
  `docs/UPSTREAM-SYNC.md`). Fork-only checks go in
  `scripts/check-fork` and `.github/workflows/fork-validate.yml`; fork-only
  tests go in `fork-tests/`, not `skills/autoreview/tests/`.

## Layout

See README.md's "Included Skills" list for the current skill inventory —
kept there as the single copy so this section can't drift out of sync with it
again.

## Safety

- Preserve pre-existing dirty/unrelated work; stage only owned paths.
- Do not commit, push, tag, or publish without explicit authorization.
- Product depth stays in README/VISION/`docs/`; keep this file operational.
