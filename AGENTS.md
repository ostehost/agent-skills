# AGENTS.md

Public shared skills for agent workflows.

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

See README.md's "Included Skills" list for the current skill inventory —
kept there as the single copy so this section can't drift out of sync with it
again.
