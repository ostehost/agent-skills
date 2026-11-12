# OpenClaw Agent Skills

![Agent Skills banner](docs/assets/readme-banner.jpg)

Shared skills for coding agents that work on OpenClaw projects.

This repo is the public canonical source for common workflows such as review
closeout and remote validation. The goal is simple: write a workflow once,
reuse it everywhere, and avoid hand-copying long `SKILL.md` files across every
repo. See [VISION.md](VISION.md) for catalog boundaries and admission principles.

## Included Skills

Each skill lives in `skills/<name>/`, listed here alphabetically.

- `agent-transcript`: local-only, redacted PR/issue transcripts, on explicit
  request only.
- `autoreview`: structured closeout/code-review workflow plus helper script.
- [`beam`](skills/beam/README.md): self-contained, authenticated, redacted
  publication of local coding sessions to a read-only OpenClaw catalog.
- `behavior-validator`: source-blind validation of user-visible behavior against
  a contract.
- `crabbox`: Crabbox/Testbox remote validation workflow for broad or CI-parity
  proof.
- `design-competition`: frontend generator-evaluator harness with Playwright or
  human review.
- `diataxis`: Diátaxis quadrant receipts and a stdlib contamination audit for
  `docs/` pages and READMEs.
- `handoff`: path-free prompt handoff workflow for delegating a task to another
  agent.
- `readme-standard`: house README structure, badge row, tone, and verification
  gates for steipete/openclaw repos.
- `session-viewer`: local searchable HTML viewer for agent session JSONL.
- `team-handoff`: start a seeded worktree session on a shared OpenClaw Gateway as
  yourself in one request.

Repo-specific product skills should stay in the repo they describe. For example,
an `acpx` usage skill belongs in `openclaw/acpx`; a general review helper belongs
here.

## Quick Start

Clone the repo:

```sh
git clone https://github.com/openclaw/agent-skills.git
cd agent-skills
```

List available skills:

```sh
scripts/install-skills --list
```

Preview an install without changing files:

```sh
scripts/install-skills --dry-run
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

Replace an existing installed skill:

```sh
scripts/install-skills --force autoreview
```

Install targets must not contain or sit inside the source skills. The installer
checks every selected destination before changing files, including with `--force`
or `--dry-run`; installing directly over the same source directory is skipped.

Symlinks are best for local development because changes in this checkout are
immediately visible. Copies are better for portable or locked-down setups.
Node-based skills declare their module format locally, so copied helpers also
run inside CommonJS projects without installing dependencies.

## Codex And Claude

For Codex, symlink this repo into `~/.codex/skills`:

```sh
mkdir -p ~/.codex/skills
ln -sfn "$(pwd)/skills" ~/.codex/skills/agent-skills
```

For Claude Code, use the target-aware installer so an existing real directory is not turned into a nested `skills/skills` link:

```sh
scripts/install-skills --target ~/.claude/skills
```

If `~/.claude/skills` already points at another shared skills folder, add
symlinks inside that folder instead:

```sh
ln -sfn "$(pwd)/skills/autoreview" /path/to/shared-skills/autoreview
ln -sfn "$(pwd)/skills/crabbox" /path/to/shared-skills/crabbox
```

Recommended one-liner for repo `AGENTS.md` files:

```text
Shared agent workflows: install or symlink https://github.com/openclaw/agent-skills for `autoreview`, `crabbox`, and other common skills. Autoreview uses one shared installation; repository entrypoints refer to it.
```

## Shared Autoreview

Install autoreview once with `python3 scripts/install-skills autoreview`. The
default `~/.agents/skills/autoreview` symlink serves every repository. On Windows,
use `python`; add `--mode copy` if symlinks are unavailable.

Repositories keep only a `.agents/skills/autoreview/SKILL.md` entrypoint copied
from [the repository template](skills/autoreview/references/repository-entrypoint.md).
Agents read the full installed skill and run its helper from the repository being
reviewed. Repo-specific review thresholds and contribution rules stay in that
repository. Helpers, fixtures, and their tests stay here.

Contribute shared improvements here first. After active reviews finish, update
this checkout once to update every symlinked consumer. Copy-mode installations
need `python3 scripts/install-skills --mode copy --force autoreview` after the
source update. Review runs do not download or update code automatically.

For pinned source archives, upgrade/rollback steps, and copy-versus-symlink
identity limits, see [source installation](docs/RELEASING.md#installing-a-pinned-source).

To compare installed helper content, run
`python3 ~/.agents/skills/autoreview/scripts/autoreview --version` (use your
custom install path when applicable). The output is `autoreview source-sha256:`
followed by the helper's SHA-256. It does not identify a release or the full skill
and does not read configuration, invoke Git or a reviewer, or write reports.

## Zero-Setup Repos

Some important repos should work for contributors who only cloned that repo and
never installed shared skills. Those repos may vendor a generated snapshot under
`.agents/skills/<name>`.

That snapshot is a distribution artifact, not the source of truth:

- edit canonical skills here first
- sync snapshots downstream after review
- keep downstream copies small in number
- add provenance and drift checks when a repo vendors a snapshot

This option does not apply to `autoreview`, which uses the shared installation
above. Vendor other operational skills only when the repo needs them available
without setup.

## Repository Layout

```text
skills/
  agent-transcript/
    SKILL.md
    scripts/
  autoreview/
    SKILL.md
    AGENTS.md
    references/
    scripts/
    tests/
  beam/
    README.md
    SKILL.md
    references/
    scripts/
  behavior-validator/
    SKILL.md
    agents/              # openai.yaml host-interface config
    references/
  crabbox/
    SKILL.md
    references/
  design-competition/
    SKILL.md
    BRIEF.yaml
    HARNESS.md
    WORKFLOW.md
    loop-config.yaml
    rubric.json / rubric.md
    .claude/agents/      # generator/evaluator/supervisor agent defs
    schemas/
    scripts/             # incl. run-axe.sh, recompute-gate.sh
    templates/
    tokens/
  diataxis/
    SKILL.md
    references/          # per-quadrant authoring rules
    scripts/             # audit_quadrant.py
    tests/
    evals/
  handoff/
    SKILL.md
  readme-standard/
    SKILL.md
  session-viewer/
    SKILL.md
    tsconfig.json
    agents/              # openai.yaml host-interface config
    scripts/             # session-viewer.ts + core/, importers/
  team-handoff/
    SKILL.md
    scripts/
fork-tests/
  autoreview/          # fork-only receipt-contract and merge-invariant tests
scripts/
  check-skills     (+ check-skills.test.py)   # upstream gate
  check-fork       (+ check-fork.test.py)     # fork-only gate
  run-checks                                  # runs both gates
  install-skills   (+ install-skills.test.py)
  validate-skills  (+ validate-skills.test.py)
  upstream-survey                             # pre-merge sync survey
```

Each skill lives in `skills/<name>/` and must contain `SKILL.md`. Helper scripts
belong inside that skill's `scripts/` directory.

## Validate

Development checks use Python 3.14 and Node.js 26, matching CI. Install the
development dependencies once, then run the shared check command:

Create the virtualenv outside this checkout. `autoreview` refuses to execute any
interpreter or tool located inside the repository under review, so an in-tree
`.venv` makes the `autoreview` self-tests below fail with `executable not found`.

```sh
python3 -m venv ~/.venvs/agent-skills
. ~/.venvs/agent-skills/bin/activate
python -m pip install -r requirements-dev.txt
npm ci --ignore-scripts
python scripts/check-skills
python scripts/check-fork
```

The check command runs frontmatter validation, syntax checks, all Python and
Node tests, and `npm run typecheck` for the session viewer. The Node packages
are development-only; installed skills do not need `npm install`. The separate
macOS CI job uses the `xcode-27` Apple Silicon runner and installs a pinned Codex CLI to exercise native sandbox access
controls without a reviewer account or provider request.

`scripts/check-skills` is upstream's shared gate. `scripts/check-fork` runs this
fork's own checks: the tests under `fork-tests/`, the `diataxis` audit tests,
`beam-handoff.test.mjs`, the `design-competition` script suites, a manifest
that fails when neither gate runs a test file, a check that every non-test
script with a shebang keeps its executable bit, and a check that the only
tracked symlinks are `.agents/rules/project.md` and `.claude/skills/diataxis`.
The script suites need bash and `jq`, so the Windows leg of
`.github/workflows/fork-validate.yml` runs `python scripts/check-fork
--skip-design-competition`; that leg also skips `beam-handoff.test.mjs`, whose
fake CLI Windows cannot run. The same workflow runs upstream's installed-source
test on a copy of the commit without those two symlinks.

`scripts/run-checks` runs `check-skills` and then `check-fork`. It refuses to
start when `TMPDIR` points into a shared scratch directory, or when the
interpreter lacks PyYAML or Pillow or lives inside this checkout.

Python autoreview suites run through `check-skills` with a fresh temporary
directory beneath the caller's home and without inherited reviewer settings or
provider credentials. The caller's home must be writable and have private storage
ancestry; do not point it at shared `/tmp`. Each fixture supplies its own
configuration. The runner preserves executable lookup,
the OS temporary directory, locale, and selected Python dependency settings,
including `PYTHONPATH`; use a trusted toolchain and dependency path. This
isolation does not apply to direct `python -m unittest` invocations, including
the separate macOS sandbox job, or to the runner's other validation commands.

On Windows, `scripts/check-skills`, its directly invoked self-test
`scripts/check-skills.test.py`, and `scripts/installed-autoreview.test.py` prepare a
restricted primary process when the current invocation does not meet
the ordinary test profile. Invoke these files directly with
Python; module (`-m`), command (`-c`), or mutated argument forms are unsupported.
They retain the selected Python interpreter, flags, arguments, working
directory, environment, standard streams,
and exit status. With a shared console, the child handles Ctrl+C while the parent
waits for its result. Failure to create or verify that process fails the test command;
it does not omit tests or change the installed skill's runtime behavior.
The child must have medium or lower integrity; lowering its integrity leaves the
original parent token unchanged. New objects default to the child’s user as owner.
The fresh token grants access to that user and SYSTEM, with matching defaults for
new objects that do not receive inherited or explicit permissions. Existing source
permissions are unchanged.
Local/domain and Entra account identities are
supported; system and virtual-service identities are not. This does not classify
how domain accounts are used. The account domain's Domain Users grant is retained;
other custom group grants may be removed by the restricted test profile.
The full native proof suite requires permission to duplicate and adjust the
current process token and create its restricted child. Missing those test
capabilities fails the requested proof even when read-only admission succeeds.

For the main runner and installed-source tests, when the original primary token
does not meet that profile, the parent runs native bootstrap proofs before
launching the child: a restricted thread cannot hide its original primary authority, a marker
cannot bypass admission, a failed parent check stops execution, and a real child
preserves invocation details. These auxiliary checks run noninteractively; an
interactive flag still applies to the requested child, without a second prompt
in the waiting parent. The restricted child runs the requested suites and
the regular invocation check. These checks establish the test process boundary;
they do not by themselves establish a skill's filesystem custody policy. The
bootstrap retains user identity grants and does not provision accounts or
rewrite file or desktop permissions. Hosts that require removed administrative
grants for their interpreter or checkout must fix that access before testing.

Compilation uses a disposable bytecode cache instead of writing into the source
checkout. Installed-source tests trust only their exact checkout for Git metadata
reads, without changing persistent Git configuration. Auxiliary proof output uses explicit
UTF-8 internally and is relayed through the caller’s text streams.

For a quick catalog check, run `scripts/validate-skills`. It checks every
`skills/*/SKILL.md` for YAML frontmatter plus required `name` and
`description` strings, and that `name` matches the skill directory.
Frontmatter must be a mapping enclosed by standalone `---` lines; trailing
spaces or tabs are allowed on the closing line. It also checks that
`skills.sh.json` is valid JSON referencing only skills that exist, each in at
most one grouping.

Session exports can contain sensitive conversation data. Treat `session-viewer`
HTML as local/private output unless it has been separately redacted and reviewed.

## Editing Rules

These rules apply to every skill in this repo.

- Keep descriptions short and useful for routing.
- Keep skill bodies operational rather than essay-like.
- Do not include secrets, private hostnames, private account IDs, or private
  URLs.
- Prefer helper scripts for repeatable command logic.
- Do not update vendored downstream snapshots by hand. Update this repo, then
  sync.

See [docs/RELEASING.md](docs/RELEASING.md) for the source-release process.

## License

MIT.
