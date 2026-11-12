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

Re-probed 2026-09-09, unchanged: the vendor-branch merge is still denied for agents, with no
mutation. The cheapest owner path needs no hook change at all -- the owner runs the merge
with a leading `!` in the agent's own session, and the agent resolves the conflicts in place.
`git push` is separately denied to agents by the launcher permission broker, so publication
is an owner step too; plan for both, not just the merge.

The guard matches on the command string, so it also fires on a merge command quoted inside
an unrelated `bash` heredoc -- documentation edits included. Write those with the file tools
rather than fighting the pattern; the guard is doing its job.

## Procedure

### 1. Survey — read-only, costs nothing

    git fetch upstream
    scripts/upstream-survey

Reports drift, the marked conflict surface, and traps 1a/1b/2/3 below. It uses
`git merge-tree --write-tree`, which computes the merge in the object store without
touching the worktree or index. Safe to run at any time, including mid-investigation.

**Rehearsal required: resolve and gate against that tree before the merge runs.** Do not
ask the owner to run the merge until a rehearsal exists for the exact upstream tip being
merged: the resolved files, a manifest of every path with its content hash and mode, an
apply script that refuses unless `HEAD`, `MERGE_HEAD` and the unmerged-path set match what
was rehearsed, and both gates green on the rehearsed tree. If upstream moves, even by one
commit, rebuild the rehearsal; the 2026-11 round was rehearsed against `16121cf`, upstream
then landed `1f71b29`, and the bundle had to be rebuilt. Check modes against the preview's
`git ls-tree -r`, not only against your own manifest: an earlier attempt lost the
executable bit on `skills/agent-transcript/scripts/agent-transcript` and passed its own
harness because the manifest carried the same error. `merge-tree` writes the real
merged tree, so `git archive <tree> | tar -x -C <scratch>` materializes exactly what the merge
will put in the worktree, conflict markers included. Resolve there, run the full gate there,
and the merge itself becomes a formality: diff each conflicted file against the preview,
confirm byte-identical, apply the resolution. On 2026-09-09 that reduced a 4-file / 9-hunk
sync to one verification step, and it front-loads traps 4 and 5 -- which otherwise surface
only after resolving -- to before the owner is asked to act at all. Keep the resolution in a
script rather than editing markers by hand: that is what makes "identical to the preview"
checkable instead of asserted, and it re-applies for free if the attempt is abandoned.

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
| Fork-only paths (`skills/design-competition/**`, `fork-tests/**`, `scripts/check-fork`, `scripts/run-checks`, `.github/workflows/fork-validate.yml`, `docs/UPSTREAM-SYNC.md`) | No conflict possible. New files at fork-only paths cost nothing at merge time — prefer adding one over editing a shared file. |
| Upstream-only additions (e.g. `skills/beam`) | Take upstream wholesale. |
| Inventory files (`README.md`, `skills.sh.json`, `AGENTS.md`) | Union, then reconcile by hand. `scripts/validate-skills` is the arbiter: it enforces that `skills.sh.json` references only existing skills, each in at most one grouping. |
| `.github/workflows/validate.yml`, `scripts/check-skills`, `scripts/check-skills.test.py` | Take upstream's files. `check-skills` and its self-test stay byte-identical to upstream; `validate.yml` is upstream's plus one line, `if: github.repository == 'openclaw/agent-skills'` on `macos-sandbox`, because the fork has no `xcode-27` runner and a queued job would block `main`'s runs. Fork-only checks go in `scripts/check-fork` and `.github/workflows/fork-validate.yml`, never into these files. |
| Fork tests of shared skills | Keep them under `fork-tests/<skill>/`. Upstream's manifest self-test requires every `skills/autoreview/tests/test_*.py` to be in its `TEST_MODULES`, so a fork test there turns upstream's gate red. |
| `skills/autoreview/scripts/autoreview` | Expect a competing rewrite; write the union by hand — see below. |

### 5. Verify

    PYTHON=<out-of-tree venv>/bin/python scripts/run-checks   # must be fully green
    scripts/upstream-survey     # drift should now read 0 behind

The gate proves the working tree, not the commit. Before committing, stage the resolution
path-limited from the rehearsal's list (every changed and added path, and both deletions),
then run the rehearsal's index check, `verify-against-preview.sh --staged <repo>`. It fails
while any path is unmerged, any index entry differs from the rehearsed tree, a rehearsed
deletion is still staged, or a rehearsed file is untracked. Staging only the conflicted
paths passes the worktree gate and still commits a tree that is missing the added files.

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
referenced them, so nothing degraded. `skills/autoreview/AGENTS.md` names
`openclaw/agent-skills` as the canonical source and says shared behaviour and fixes belong
upstream. (Until the 2026-11 sync that rule lived in `skills/autoreview/CLAUDE.md`, which
upstream deleted.)

Use the gated `fork-tests/autoreview/test_receipt_contract.py` as the specification for the
re-applied receipt layer, and the survey's trap-1a list as the re-application checklist.

**2026-08-20 refinement: decide the fork's policy questions BEFORE resolving, and the
construction follows from them.** That round asked the owner two questions up front —
keep or yield panels and `--parallel-tests`, and keep or take `SKILL.md` — and both
answers were "yield". With the competition settled in advance, "write the union by hand"
stopped meaning "edit 30 conflict regions in a 22,000-line conflicted file" and became
"take upstream's file as the base, then re-apply the fork layer onto it". Same union,
built by construction rather than by marker-editing, and far less error-prone. The
warning above still stands for the case where the two sides genuinely compete: settle
the competition first, then pick the cheaper construction.

Re-applying the receipt layer means its **dependency closure**, not just the trap-1a list.
Two symbols that list does not name were needed: `is_structured_output_failure` (upstream
deleted it, but `classify_receipt_error` calls it) and the `args.model_used` assignment on
the Codex success path (the receipt attests which model actually ran after a Sol-to-Terra
retry). Both were caught by the gated suite, not by the survey. Conversely, resist
re-applying fork code that carries no behaviour: `_ActivityStreamDisplay` was a pure DRY
refactor of bookkeeping upstream duplicates, with no test and no contract, so it was
dropped to shrink the delta.

**Taking an upstream test file wholesale can lose a local environment adaptation.** The
fork had added `GIT_CONFIG_GLOBAL`/`GIT_CONFIG_NOSYSTEM`/`GIT_CONFIG_SYSTEM` to the `git()`
helper in `test_autoreview_hardening.py`, keeping its temporary repos hermetic. Upstream's
copy lacks them, so a clean "take upstream" made 16 tests fail on this machine: the
inherited `core.hooksPath` commit-msg hook rejects the fixtures' plain commit messages.
This is a trap-4 sibling worth its own check — after taking an upstream test file, run it
before assuming it is fine, and re-apply any local hermeticity the fork had added. It is
also a good upstreaming candidate: it costs upstream nothing and makes the suite hermetic
for every contributor.

## Invariants that must not move

**The interpreter guard.** `find_command`, `first_executable_candidate`, `is_within`, and
`has_directory_component` implement autoreview's refusal to execute any interpreter located
inside the repository under review. After a sync the merged file must hash exactly as
upstream's does. Until 2026-09-09 all three sides hashed to `sha256` prefix
`5b3d5b7497fc217c`. Upstream changed these functions between `b86a912` and `1f71b29`, so
from the 2026-11 sync on, upstream and the merged file hash to `ffed4e0d42cbb687`:

    for ref in "$(git merge-base upstream/main HEAD)" upstream/main HEAD; do
      git show "${ref}:skills/autoreview/scripts/autoreview" \
        | awk '/^def (find_command|first_executable_candidate|is_within|has_directory_component)/,/^$/' \
        | shasum -a 256 | cut -c1-16
    done

Note the braces. Written as `"$ref:skills/..."` this silently breaks under zsh, which reads
`:s` as a parameter modifier: `git show` then gets an empty ref, awk sees nothing, and the
command prints `e3b0c44298fc1c14` — the sha256 of empty input — for all three refs. Three
matching hashes look like a pass. If you see `e3b0c44298fc1c14`, the check did not run.

A merged hash that differs from upstream's is a defect, not a resolution. Re-pin the value
here when upstream changes it.

Practical consequence: `scripts/run-checks` must not hand autoreview an in-repo interpreter.
It has no `.venv` fallback. It refuses to start when `$PYTHON` (default `python3`) lives
inside the checkout, lacks PyYAML or Pillow, or resolves its temporary directory into the
checkout or, on macOS, a shared scratch directory such as `/tmp`. Autoreview refuses those
temporary roots, so a run under one fails about 134 tests for environment reasons only.

**Gate split.** `scripts/run-checks` runs upstream's `scripts/check-skills` (CI:
`validate.yml`), then the fork's `scripts/check-fork` (CI: `fork-validate.yml`, an
`ubuntu-latest` leg and a `windows-latest` leg with `--skip-design-competition`). There is
no hand-kept mirror to update: `check-fork` derives what `check-skills` covers from its
`TEST_MODULES` and command list, and its manifest fails when a test file is run by neither
gate. `check-fork` also fails when a non-test script with a shebang has lost its executable
bit, which no suite notices when it invokes the script through an interpreter.

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
| 2026-08-10 | `94b2193` | **`95e443f` (unchanged)** | 12 behind / 54 ahead | **Cherry-picked, not merged.** *Corrected 2026-08-20:* this row originally claimed merge commit `24b631f` and merge-base `94b2193`. Neither exists in this history — `git log --merges` shows nothing after `42bc00d`, and the base never moved off `95e443f`. The round was twelve cherry-picks of `#161`-`#174`; the content landed faithfully (`beam`, `crabbox`, `readme-standard`, `behavior-validator` were byte-identical to upstream at `94b2193`) but no second parent was recorded. Cost, paid on 2026-08-20: two of that sync's six conflicts existed *only* because the base was stale, and the survey's Trap 1b list inflated to 110+ symbols mixing real deletions with frozen-base artifacts. This is the playbook's own warning, observed. Adopted upstream's isolated Amp engine, owned process-group cleanup, real dry-run preflight, JavaScript secret-reference handling, Windows/OpenCode portability fixes, session timestamp guard, `readme-standard` skill, and setup-action updates. Preserved the fork's digest-bound receipts, bounded failed-review test cleanup, structured-output retries, and design catalog entry. Added the shared `numberValue` helper needed by the fork-refactored session importer. `scripts/run-checks` passed; the interpreter-guard hash remained `5b3d5b7497fc217c`; post-merge drift is 0 behind / 55 ahead. |
| 2026-08-20 | `88f8500` | `88f8500` | 23 behind / 68 ahead | **Synced.** 6 conflicts / 63 hunks — but only 11 of the 23 commits carried new content; 12 were the 08-10 cherry-picks re-presented by the stale base. Two conflicts (`skills.sh.json`, `pi-openclaw.ts`) were pure stale-base artifacts, resolved `--ours` after verifying the fork already carried the content. Upstream contracted hard: `autoreview` went 13,215 -> 6,034 lines across four unreviewed direct-to-main pushes (`4e3f4cf`, `ae1eebc`, `1ef3fab`, `ca100e6`). **Two owner decisions:** yield panels and `--parallel-tests` to upstream's removal, and take `SKILL.md` wholesale per `skills/autoreview/CLAUDE.md`. That collapsed three more conflicts to `git checkout upstream/main --`, leaving one real file. Adopted upstream's fail-closed TruffleHog pack scanning (replacing the whole local secret classifier), bounded engine runtime (`--engine-timeout-seconds`), portable Fable selector, strict beam share URLs, and crabbox portability. Preserved the receipt layer by construction — upstream's file as the base, the 17-symbol fork layer re-applied on top — verified against all 30 remaining `test_receipt_contract` tests. Retired 2 of its 32 tests (`parallel_tests_failed`, `allow_partial_panel`) as dead with the dropped features. `scripts/run-checks` green; 229 Python tests; interpreter guard still `5b3d5b7497fc217c`. |
| 2026-09-02 | `0cdce54` | `0cdce54` | 27 behind / 69 ahead | **Synced by true merge.** This merge commit records upstream as its second parent; 4 conflicted files / 15 hunks matched the pre-merge survey. Adopted upstream's exact Git-source capture, complete mixed-target/evidence batching, pre-send rescans, raw-parent checks, preparation progress, Node 26 CI, bounded transcript discovery/reads, shell-free Windows session opener, Beam URL support, and Crabbox guidance. Preserved the fork's digest-bound receipt layer, immutable target/scope expectations, stdout-marker neutralization, transcript head/tail publication and redaction hardening, session-viewer parser parity tests, and design-competition gates. Retired the obsolete truncation-producer merge invariants after upstream replaced truncation with lossless `CapturedBundle`/evidence partitioning; the fork-only receipt symbol guard remains. `scripts/run-checks` passed with 285 Python tests, 122 Node tests, and both design-competition suites; the interpreter guard remained `5b3d5b7497fc217c`. |
| 2026-09-09 | `b86a912` | `b86a912` | 14 behind / 70 ahead | **Synced by true merge.** 4 conflicted files / 9 hunks, exactly as the pre-merge survey predicted. The whole resolution was built and gated against `git merge-tree --write-tree` output *before* the merge ran, then applied to a worktree verified byte-identical to that preview. **Owner decision: yield TruffleHog to upstream's scanner-free policy (#240).** That is a deliberate posture change, not a mechanical resolution: the fail-closed pre-send scan of outgoing review packs is gone, replaced by upstream's prompt-level "report suspected credentials as P0" instruction. Chosen for delta minimization and because `skills/autoreview/CLAUDE.md` forbids repo-local behavior variants; upstream requires an explicit maintainer decision to reintroduce a scanner. It cost the fork-only receipt suite its `add_fake_trufflehog` stub (trap 1b), replaced by an explicit `PATH` prepend for the fake codex binary. Adopted upstream's `--status-output` sidecar, trusted OpenAI Responses route projection, caller-`HOME` auth helper, Claude capability-probe fix, session-viewer bounded reads, and Beam receiver limits. Preserved the receipt layer by construction: upstream's regions plus the fork's `args.model_used` attestation, `--receipt-output` path rejection, commit-SHA freezing, target binding, and the outer error-receipt `try/except` — with `write_review_status` threaded into both the fork's `run_review_passes` call site and its exit path. **Two silent defects the marked conflicts did not show:** the auto-merge produced a duplicate `buildSessionViewerHtml` import in `session-viewer.test.ts` (a SyntaxError with no conflict marker, both sides having added it), and the baseline was already red before the merge — `agent-transcript.test.mjs` ran `find` with no `--root`, walked the machine's real session logs, and tripped the 20,000-file discovery cap before reaching its assertion. Fixed hermetically; that is the same trap-4 sibling this playbook already documents. `scripts/run-checks` green: 315 Python tests (285 before), 133 Node tests, both design-competition suites; interpreter guard still `5b3d5b7497fc217c`. |
| 2026-11-12 | `1f71b29` | `1f71b29` | 129 behind / 75 ahead | **Merged by the owner from a rehearsed resolution.** 14 conflicted files. The first rehearsal was built against `16121cf`; upstream then landed `1f71b29` (#391, a Beam fix), and the bundle was rebuilt from scratch, which is why the playbook now requires a rehearsal for the exact tip. **Owner decisions D1-D9:** upstream's `check-skills`, its self-test and `validate.yml` stay upstream's (plus one `macos-sandbox` repository guard), with fork checks moved to the new `scripts/check-fork` and `fork-validate.yml` (`ubuntu-latest` and `windows-latest --skip-design-competition`); the fork's receipt and merge-invariant tests moved to `fork-tests/autoreview/` because upstream's manifest self-test rejects unlisted tests under `skills/autoreview/tests/`; `install-skills` takes upstream's overlap refusal but keeps the fork's empty-catalog guard; upstream's npm dev dependency and Pillow pin are accepted; no secret scanner. Receipt layer re-applied onto upstream's file by construction: `model_used` carried back across upstream's `copy.copy(args)`, `interrupted` error kind, redaction before the digest, `--native-handoff` refused with `--receipt-output`, and, for local/branch targets, the base ref pinned and re-checked (including an A-B-A move and a move during the review) instead of rewriting the ref name to a SHA. An adversarial mutation pass found receipt behaviours no test pinned (status mapping for incomplete/filtered/incorrect reviews, three of four marker-neutralization sites, the reviewer key set, `--expect-*` without a receipt); each now has a test, and 65 of 67 receipt-layer mutants die (2 are equivalent). `check-fork` now also fails on a shebang script that lost its executable bit. Yielded to upstream the fork's `xcrun_db` exclude hunk in `test_autoreview_hardening.py`, which the 2026-09-09 resolution had added to keep a macOS `xcrun` cache out of one temp-root fixture; upstream's version passed 5 of 5 local macOS runs, so restore the exclude if that test flakes again. Rehearsed gates green: `check-skills --group all` 780 Python tests (16 skipped), 156 Node tests, typecheck; `check-fork` 180 Python tests, 5 Node tests, both design-competition suites; interpreter guard re-pinned to `ffed4e0d42cbb687`, equal to upstream. |
