# Upstream integration playbook

How to pull `openclaw/agent-skills` into this fork without losing work. Read this before
starting a sync; append to the log at the bottom when one lands.

## The model you are in

This is the **vendor branch** pattern. A pristine, never-edited copy of upstream lives on
its own ref — `upstream/main` *is* the vendor branch — and integration is a **three-way
merge** using the last import as common ancestor. The operation is an **upstream sync**.

The mechanical fact that drives every decision below: **only a true merge records a second
parent, and the second parent is what advances the merge base.** Cherry-pick and squash are
*integration without ancestry* — the content arrives, the ancestry does not. Git still
believes the common ancestor is the old one, so every later sync re-presents the same
conflicts from the same frozen base. That is why merge is the standard recommendation for a
fork that intends to keep tracking, and why the shortcuts get more expensive each round.

## The lane constraint

This machine enforces a main-only lane through a `dcg.sh` PreToolUse hook. The lane
implements **trunk-based development**: linear history, one shared main, all changes
originating in-repo. It has no model for an external source line — the token `upstream`
appears nowhere in `dcg.sh`, `CLAUDE.md`, or `AGENTS.md`.

Probed 2026-08-02, each by actual attempt (none mutated anything):

| Operation | What practice calls it | Result |
| --- | --- | --- |
| `git merge upstream/main` | vendor-branch merge; advances the base | **denied by hook** |
| `git merge --squash upstream/main` | vendor drop; **creates no merge commit** | **denied by hook** |
| `git rebase --onto upstream/main …` | patch-queue replay; linear history | **denied by hook** |
| `git rebase upstream/main` | — | **denied by hook** |
| `git merge --ff-only upstream/main` | — | refused by git; histories diverged |
| `git cherry-pick` | integration *without* ancestry | **permitted** (ask-rule) |

The hook classifies on the **verb, not the resulting topology**. Its message cites merge
commits on shared main, but `--squash` produces none and is blocked anyway, and `--onto`
produces linear history and is blocked anyway. Meanwhile the one permitted method is the one
best practice ranks worst here.

This is a gap, not a policy disagreement. An agent must not route around it — not with
`bash -c` wrapping, not with `commit-tree`/`update-ref` plumbing, not with a
`worktree add -b` that merges elsewhere and fast-forwards main onto the result. Each of
those reaches a hook-denied topology by another path. Doctrine is explicit that a rule which
must hold every time lives in the hook.

**So a sync needs the repository owner to act.** Either they run the merge themselves, or
they narrow the hook first. If narrowing: pin the **literal** string `upstream/main`, never
a glob. `git fetch` is unclassified, so a pattern like `upstream/sync-*` lets anyone fetch
an arbitrary SHA into a matching ref name and mint themselves merge authority.

## Procedure

### 1. Survey — read-only, costs nothing

    git fetch upstream
    scripts/upstream-survey

Reports drift, the marked conflict surface, and traps 1a/1b/2/3 below. It uses
`git merge-tree --write-tree`, which computes the merge in the object store without
touching the worktree or index. Safe to run at any time, including mid-investigation.

### 2. Gate before you resolve, not after

Every behaviour you care about must have a test that runs in `scripts/run-checks` **before**
the merge starts. A merge resolution is judged by a green suite; anything ungated is
invisible to that judgement. Check `git log --diff-filter=A` for test files nobody wired up
— `test_receipt_contract.py` sat green and unexecuted for months, and it is the only
specification of the fork's flagship feature.

Enable `rerere` so an abandoned attempt does not cost the resolutions twice:

    git config rerere.enabled true

### 3. Authorize

Present the owner with: the drift, the conflict surface, the survey's trap sections, and
the explicit statement that one merge commit will exist on `main` permanently. Do not
describe a workaround as hook-legal — if it reaches a denied topology, say so.

### 4. Resolve, by file class

| Class | Policy |
| --- | --- |
| Fork-only paths (`skills/design-competition/**`, `scripts/run-checks`, `docs/UPSTREAM-SYNC.md`) | No conflict possible. New files at fork-only paths cost nothing at merge time — prefer adding one over editing a shared file. |
| Upstream-only additions (e.g. `skills/beam`) | Take upstream wholesale. |
| Inventory files (`README.md`, `skills.sh.json`, `AGENTS.md`) | Union, then reconcile by hand. `scripts/validate-skills` is the arbiter: it enforces that `skills.sh.json` references only existing skills, each in at most one grouping. |
| `.github/workflows/validate.yml` | Take upstream's structure, re-apply the fork's steps (design-competition suites, the extra test modules). Then mirror the result into `scripts/run-checks` — the `python tests` module list must stay byte-identical between the two. |
| `skills/autoreview/scripts/autoreview` | Expect a competing rewrite; write the union by hand — see below. |

### 5. Verify

    scripts/run-checks          # must be fully green
    scripts/upstream-survey     # drift should now read 0 behind

Then confirm the invariant anchors below by hand. Traps 4 and 5 surface only here, so a
red suite after a clean-looking resolution is expected — read each failure before assuming
the resolution was wrong.

### 6. Record

Append to the log at the bottom of this file and re-run the survey to refresh the pins.

## The silent traps

Marked conflicts get read by whoever resolves them. These produce **no conflict marker**,
which is why they are the ones that land unnoticed. `scripts/upstream-survey` detects them by
diffing ASTs rather than text, and it scans **every** changed Python file, not only the
conflicted ones -- a clean auto-merge is exactly where this damage hides.

**Trap 1a -- fork-added symbols.** The fork invented them, so resolving a file as "take
upstream" removes them silently. Never hand-enumerate this: before the 2026-08-02 sync an
eyeballed review found 6 of the 15 in `skills/autoreview/scripts/autoreview`.

**Trap 1b -- upstream-deleted symbols.** Also absent upstream, but for the opposite reason:
they were in the merge base and upstream removed them. Dropping these is usually *correct*.
The 2026-08-02 sync found exactly one, `unified_diff_metadata`, superseded by
`redact_deletion_only_secret_values`. A two-way fork-vs-upstream diff calls it a fork feature
and is wrong -- always classify against the merge base.

**Trap 2 -- signature drift.** A function exists on both sides with different parameters or
return type. If some call sites conflict and others auto-merge, a resolution mixes conventions.

> Not hypothetical. During the 2026-08-02 merge the three `*_bundle` functions conflicted and
> took upstream's `bool`, while `load_extra_prompt` and `load_datasets` auto-merged silently
> and kept the fork's `list[str]`. `main()` ended up combining both.
> `test_merge_invariants` caught it; nothing else would have.

Drift also reaches *tests*, which the tool does not scan. Upstream threaded
`known_secret_fragments_out` through `commit_bundle`, and a fork-only test stubbed it with the
old 2-arg signature -- a `TypeError` at run time, not merge time. After any drift is reported,
grep fork-only tests for stubs and `Namespace(...)` literals of the changed functions.

**Trap 3 -- new options with restrictive defaults.** Upstream adds a CLI flag whose default
narrows existing behaviour. Nothing conflicts and nothing fails to import, but runs behave
differently and fixtures written before the flag stop matching. The 2026-08-02 sync hit this
with `--max-priority` (default `P0`), which filtered out the `P1` findings three fork-only
tests depended on.

**Trap 4 -- new required external tools.** Upstream can make a binary mandatory. `#145` made
TruffleHog a required preflight, and CI does not install it; upstream's own tests stub it via
`add_fake_trufflehog`. Fork-only tests that predate the dependency need the same stub. Watch
for new `resolve_command` / `SystemExit("... is required ...")` calls.

**Trap 5 -- assertion string collisions.** New output lines can collide with loose assertions.
`assertNotIn("clean", stdout)` began failing purely because the preflight now prints
`trufflehog: clean (0.7s)`. Narrow the assertion; do not weaken it.

Traps 1a, 1b, 2 and 3 are reported by `scripts/upstream-survey`. Traps 4 and 5 surface only
when the gated suite runs, which is why step 2 comes before step 4.

## `skills/autoreview/scripts/autoreview` — expect a competing rewrite

14 of the 23 hunks were in this one file. This playbook previously said to resolve it as an
ownership transfer -- take upstream wholesale, re-apply the fork layer. **Reading the hunks
showed that was wrong**, and the same check is worth repeating before committing to any
strategy: both sides had rewritten `main()` in different directions. Taking either side
wholesale would have silently dropped either the receipt layer or the entire security backlog.

What worked was writing the union by hand, region by region:

- Upstream owns the bundle functions, secret-fragment threading, preflight, prompt chunking,
  priority thresholds, and the new engines.
- The fork's receipt layer, commit-SHA freezing, target binding and `_ActivityStreamDisplay`
  are re-applied on top, inside the fork's outer `try/except` that writes error receipts.
- Where the two genuinely competed, decide **on the merits and record why**. From 2026-08-02:
  the fork's bounded `finish_parallel_tests(timeout=10)` was kept because upstream's plain
  `finally` can hang on a failed review; Droid's `xhigh`/`max` thinking levels were kept
  alongside upstream's new Kimi levels.

Where the fork's divergence carries no real benefit, **yield to upstream to shrink the delta**.
The fork's `list[str]` truncation reasons became upstream's `bool`:
`ensure_reviewer_input_complete` already accepted both and the receipt contract never
referenced them, so nothing degraded. `skills/autoreview/CLAUDE.md` is explicit that this file
is canonical upstream and must not carry repo-local behaviour variants.

Use the gated `test_receipt_contract` (32 tests) as the specification for the re-applied
receipt layer, and the survey's trap-1a list as the re-application checklist.

## Invariants that must not move

**The interpreter guard.** `find_command`, `first_executable_candidate`, `is_within`, and
`has_directory_component` implement autoreview's refusal to execute any interpreter located
inside the repository under review. They are byte-identical across merge-base, upstream, and
fork — `sha256` prefix `5b3d5b7497fc217c`:

    for ref in "$(git merge-base upstream/main HEAD)" upstream/main HEAD; do
      git show "${ref}:skills/autoreview/scripts/autoreview" \
        | awk '/^def (find_command|first_executable_candidate|is_within|has_directory_component)/,/^$/' \
        | shasum -a 256 | cut -c1-16
    done

Note the braces. Written as `"$ref:skills/..."` this silently breaks under zsh, which reads
`:s` as a parameter modifier: `git show` then gets an empty ref, awk sees nothing, and the
command prints `e3b0c44298fc1c14` — the sha256 of empty input — for all three refs. Three
matching hashes look like a pass. If you see `e3b0c44298fc1c14`, the check did not run.

Any post-merge difference there is a defect, not a resolution.

Practical consequence: `scripts/run-checks` must not hand autoreview an in-repo interpreter.
The repo's own `.venv/` is refused by design, so the script uses `python3` from PATH and
falls back to `.venv` only for the two steps that import PyYAML.

**Gate mirroring.** `scripts/run-checks` mirrors `.github/workflows/validate.yml` step for
step, by hand. Whenever one changes, change the other in the same commit.

## Why this fork exists, and the exit

Every fork-only change is a permanent integration tax, paid again at every sync. The
strategic best practice is **delta minimization**: upstream what you can, so the fork
shrinks toward zero. Candidates here are the receipt contract and `skills/design-competition`
(fork-only, absent upstream). Reducing the delta is worth more than getting good at merging.

`agent-skills` carries a blanket waiver from the workspace's eight-entry-point command
contract, precisely to stay byte-aligned with upstream — see `config/WORKFLOW.md`. Do not
add a justfile here.

## Sync log

| Date | Upstream tip | Merge-base after | Drift before | Notes |
| --- | --- | --- | --- | --- |
| 2026-08-02 | `95e443f` | `95e443f` | 66 behind / 48 ahead | **Synced.** Merge commit `42bc00d`; 8 conflicts / 23 hunks. The owner ran `git merge upstream/main` by hand — the hook denies it for agents. Tests 267 → 378. Closed the TruffleHog and `RecursionError` gap on the redaction path (`trufflehog` refs 0 → 31). Adopted upstream's `bool` truncation convention. Dropped `unified_diff_metadata` as a supersession, not a fork feature. All five trap classes fired; each is documented above because each cost time. |
| 2026-08-10 | `94b2193` | `94b2193` | 12 behind / 54 ahead | **Synced.** Merge commit `24b631f`; 5 conflicts / 9 hunks. Adopted upstream's isolated Amp engine, owned process-group cleanup, real dry-run preflight, JavaScript secret-reference handling, Windows/OpenCode portability fixes, session timestamp guard, `readme-standard` skill, and setup-action updates. Preserved the fork's digest-bound receipts, bounded failed-review test cleanup, structured-output retries, and design catalog entry. Added the shared `numberValue` helper needed by the fork-refactored session importer. `scripts/run-checks` passed; the interpreter-guard hash remained `5b3d5b7497fc217c`; post-merge drift is 0 behind / 55 ahead. |
