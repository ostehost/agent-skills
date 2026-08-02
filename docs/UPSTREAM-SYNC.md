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

Reports drift, the marked conflict surface, and both silent traps below. It uses
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

Present the owner with: the drift, the conflict surface, the survey's two trap sections, and
the explicit statement that one merge commit will exist on `main` permanently. Do not
describe a workaround as hook-legal — if it reaches a denied topology, say so.

### 4. Resolve, by file class

| Class | Policy |
| --- | --- |
| Fork-only paths (`skills/design-competition/**`, `scripts/run-checks`, `docs/UPSTREAM-SYNC.md`) | No conflict possible. New files at fork-only paths cost nothing at merge time — prefer adding one over editing a shared file. |
| Upstream-only additions (e.g. `skills/beam`) | Take upstream wholesale. |
| Inventory files (`README.md`, `skills.sh.json`, `AGENTS.md`) | Union, then reconcile by hand. `scripts/validate-skills` is the arbiter: it enforces that `skills.sh.json` references only existing skills, each in at most one grouping. |
| `.github/workflows/validate.yml` | Take upstream's structure, re-apply the fork's steps (design-competition suites, the extra test modules). Then mirror the result into `scripts/run-checks` — the `python tests` module list must stay byte-identical between the two. |
| `skills/autoreview/scripts/autoreview` | Ownership transfer — see below. |

### 5. Verify

    scripts/run-checks          # must be fully green
    scripts/upstream-survey     # drift should now read 0 behind

Then confirm the invariant anchors below by hand.

### 6. Record

Append to the log at the bottom of this file and re-run the survey to refresh the pins.

## The two silent traps

Marked conflicts get read by whoever resolves them. These produce **no conflict marker**,
which is why they are the ones that land unnoticed. `scripts/upstream-survey` detects both
by diffing ASTs rather than text, and it scans **every** changed Python file, not only the
conflicted ones — a clean auto-merge is exactly where this damage hides.

**Trap 1 — deletion by replacement.** A symbol exists only in the fork, so resolving a file
as "take upstream" removes it silently, with no failing test if nothing referenced it. As of
2026-08-02 there are **16** such functions in `skills/autoreview/scripts/autoreview`. An
eyeballed review found 6 of them; the tool found all 16. Never hand-enumerate this.

**Trap 2 — signature drift.** A function exists on both sides with different parameters or
return type. If some call sites conflict and others auto-merge, a resolution can mix the two
conventions. The live examples:

- **Truncation type.** Five producers (`local_bundle`, `branch_bundle`, `commit_bundle`,
  `load_extra_prompt`, `load_datasets`) return `tuple[str, list[str]]` here and
  `tuple[str, bool]` upstream. `main()` composes them with `[*a, *b, *c]` here versus
  `a or b or c` upstream. Splatting a `bool` is a runtime `TypeError`.
- **Parameter threading.** Upstream threads `javascript_dialect: str | None` through the
  whole secret-risk chain (`secret_text_risk`, `secret_literal_risk`, `call_arguments_risk`,
  `fallback_secret_risk`, `require_no_secret_values`, `safe_secret_*_suffix`) and
  `known_secret_fragments_out: set[str] | None` through the bundle and patch chain.
  `validate_review_patch` gains four parameters. Take a callee's new signature without its
  call sites and you get a `TypeError` git never warned about.

Both are pinned by `skills/autoreview/tests/test_merge_invariants.py`, which is gated. Every
assertion in it was mutation-tested: reverting a producer to upstream's `bool`, switching
`main()` to `or`, renaming a fork-only function, and swapping the UTF-16BE key sort for a
plain one each turn the suite red. Delete that file once the fork tracks upstream again.

## `skills/autoreview/scripts/autoreview` — ownership transfer, not a hand-merge

14 of the 23 hunks are in this one file, and upstream has 56 commits to the fork's 11 since
the merge-base. Do not hand-merge it. **Take upstream's file wholesale, then re-apply the
fork's receipt layer** using the gated `test_receipt_contract` suite (32 tests) as its
specification. The 16 fork-only functions listed by the survey are the re-application
checklist.

The reason this matters is not tidiness. Most of upstream's 56 commits are fixes to the
**secret-redaction path this fork already ships and runs** — `autoreview` strips credentials
out of diffs before shipping them to a third-party review engine. Measured 2026-08-02:

| Signal | fork | upstream |
| --- | --- | --- |
| `trufflehog` references (heuristics → TruffleHog migration) | 0 | 31 |
| `RecursionError` handlers (fail closed on deep structures) | 0 | 1 |

Being behind here is a credential-leak patch backlog, not feature lag.

## Invariants that must not move

**The interpreter guard.** `find_command`, `first_executable_candidate`, `is_within`, and
`has_directory_component` implement autoreview's refusal to execute any interpreter located
inside the repository under review. They are byte-identical across merge-base, upstream, and
fork — `sha256` prefix `5b3d5b7497fc217c`:

    for ref in "$(git merge-base upstream/main HEAD)" upstream/main HEAD; do
      git show "$ref:skills/autoreview/scripts/autoreview" \
        | awk '/^def (find_command|first_executable_candidate|is_within|has_directory_component)/,/^$/' \
        | shasum -a 256 | cut -c1-16
    done

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
| 2026-08-02 | `95e443f` | *(not synced)* | 66 behind / 48 ahead | Surveyed, gated, and documented. Merge **not** performed — needs owner authorization for one merge commit. Pins: merge-base `4664d27da471d1cb71bebdd9845dc8a6c56d6bbe`, fork tip `61df836`. |
