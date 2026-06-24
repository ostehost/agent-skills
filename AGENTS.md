# AGENTS.md

Public shared skills for agent workflows.

## Rules

- Canonical shared skills live under `skills/<name>/SKILL.md`.
- Keep repo-specific workflows out unless they are useful as public examples.
- Keep secrets, private hostnames, private account IDs, and private URLs out.
- Skill descriptions: short trigger phrase, not full documentation.
- Skill bodies: operational, terse, current.
- Helper scripts belong under `skills/<name>/scripts/`.
- Validate after edits: `scripts/validate-skills`.
- Do not edit generated/vendor copies in downstream repos; update here, then sync.

## Architecture

- Helper scripts are zero-dependency and directly runnable: no `package.json`,
  lockfile, `node_modules`, or build/bundle step. They run straight from the
  language runtime (`ruby`, `python3`, `node`; `.ts` via Node type-stripping).
  Do not add a package manager, bundler, or third-party dependency — direct
  symlink/copy installs are the point.
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

- `skills/autoreview`: shared closeout/code-review helper.
- `skills/crabbox`: shared Crabbox/Testbox remote validation workflow.
