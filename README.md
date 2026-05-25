# OpenClaw Agent Skills

Shared skills for coding agents that work on OpenClaw projects.

This repo is the public canonical source for common workflows such as review
closeout and remote validation. The goal is simple: write a workflow once,
reuse it everywhere, and avoid hand-copying long `SKILL.md` files across every
repo.

## Included Skills

- `autoreview`: structured closeout/code-review workflow plus helper script.
- `crabbox`: Crabbox/Testbox remote validation workflow for broad or CI-parity
  proof.
- `handoff`: path-free prompt handoff workflow for delegating a task to another
  agent.

Repo-specific product skills should stay in the repo they describe. For example,
an `acpx` usage skill belongs in `openclaw/acpx`; a general review helper belongs
here.

## Quick Start

Clone the repo:

```sh
git clone https://github.com/openclaw/agent-skills.git
cd agent-skills
```

Install all skills into the default agent skill directory:

```sh
scripts/install-skills
```

Install only selected skills:

```sh
scripts/install-skills autoreview crabbox
```

Install somewhere else:

```sh
scripts/install-skills --target ~/.codex/skills autoreview
```

Use copies instead of symlinks:

```sh
scripts/install-skills --mode copy --target ~/.agents/skills
```

Symlinks are best for local development because changes in this checkout are
immediately visible. Copies are better for portable or locked-down setups.

## Codex And Claude

For Codex, symlink this repo into `~/.codex/skills`:

```sh
mkdir -p ~/.codex/skills
ln -sfn "$(pwd)/skills" ~/.codex/skills/agent-skills
```

For Claude Code, symlink this repo into `~/.claude/skills`:

```sh
mkdir -p ~/.claude
ln -sfn "$(pwd)/skills" ~/.claude/skills
```

If `~/.claude/skills` already points at another shared skills folder, add
symlinks inside that folder instead:

```sh
ln -sfn "$(pwd)/skills/autoreview" /path/to/shared-skills/autoreview
ln -sfn "$(pwd)/skills/crabbox" /path/to/shared-skills/crabbox
```

Recommended one-liner for repo `AGENTS.md` files:

```text
Shared agent workflows: install or symlink https://github.com/openclaw/agent-skills for `autoreview`, `crabbox`, and other common skills; do not vendor shared skills here unless this repo intentionally needs a zero-setup snapshot.
```

## Zero-Setup Repos

Some important repos should work for contributors who only cloned that repo and
never installed shared skills. Those repos may vendor a generated snapshot under
`.agents/skills/<name>`.

That snapshot is a distribution artifact, not the source of truth:

- edit canonical skills here first
- sync snapshots downstream after review
- keep downstream copies small in number
- add provenance and drift checks when a repo vendors a snapshot

`autoreview` is a good candidate for a zero-setup snapshot in flagship repos
because review closeout is part of the contribution workflow. Large operational
skills should be vendored only when the repo genuinely needs them available
without setup.

## Repository Layout

```text
skills/
  autoreview/
    SKILL.md
    scripts/
  crabbox/
    SKILL.md
  handoff/
    SKILL.md
scripts/
  install-skills
  validate-skills
```

Each skill lives in `skills/<name>/` and must contain `SKILL.md`. Helper scripts
belong inside that skill's `scripts/` directory.

## Validate

Run this after edits:

```sh
scripts/validate-skills
```

The validator checks every `skills/*/SKILL.md` for YAML frontmatter plus required
`name` and `description`.

## Editing Rules

- Keep descriptions short and useful for routing.
- Keep skill bodies operational rather than essay-like.
- Do not include secrets, private hostnames, private account IDs, or private
  URLs.
- Prefer helper scripts for repeatable command logic.
- Do not update vendored downstream snapshots by hand. Update this repo, then
  sync.

## License

MIT.
