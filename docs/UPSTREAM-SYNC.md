# Upstream sync record

This fork tracks `openclaw/agent-skills`. This file records the drift, the pins, and the
traps a future sync must not walk into. Update it every time a sync lands.

## Pins as of 2026-08-02

| | |
| --- | --- |
| merge-base | `4664d27da471d1cb71bebdd9845dc8a6c56d6bbe` |
| upstream tip at survey | `95e443f7275dad22efbb79fbdf93788c4b22db1a` |
| fork tip at survey | `393c6afdb5f0cee1bc4fc3b57e670a9cd0081d62` |
| drift | 66 behind / 47 ahead |

Fork-only skill: `skills/design-competition` (absent upstream).
Upstream-only skill: `skills/beam` — added upstream **after** the merge-base, so the fork
never had it and never deleted it. It arrives as a clean addition, not a conflict.

## Why this sync is not cosmetic

56 of the 66 upstream commits touch `skills/autoreview/scripts/autoreview`, and most are
fixes to the **secret-redaction path this fork already ships and runs**.
`secret_assignment_matches`, `secret_text_risk`, `require_no_secret_values`,
`file_bundle_snapshot`, and `safe_untracked_file_snapshots` all exist here today, inherited
from the merge-base. Measured gaps:

| Signal | fork | upstream |
| --- | --- | --- |
| `trufflehog` references (heuristics to TruffleHog migration) | 0 | 31 |
| `RecursionError` handlers (fail-closed on deep structures) | 0 | 1 |

That is a credential-leak patch backlog on a live code path: `autoreview` strips secrets out
of diffs before shipping them to a third-party review engine.

## Conflict surface

Preview it without touching the worktree:

    git merge-tree --write-tree upstream/main HEAD

As of the pins above: 8 files, 23 hunks.

| File | Hunks |
| --- | --- |
| `skills/autoreview/scripts/autoreview` | 14 |
| `skills/autoreview/tests/test_autoreview_hardening.py` | 3 |
| `.github/workflows/validate.yml` | 1 |
| `AGENTS.md` | 1 |
| `README.md` | 1 |
| `skills.sh.json` | 1 |
| `skills/autoreview/SKILL.md` | 1 |
| `skills/crabbox/SKILL.md` | 1 |

## The two silent traps

Marked conflicts get read. These do not produce a conflict marker, and are the real risk.

**1. Truncation type drift.** The five truncation producers disagree across the two sides:

| | `local_bundle` / `branch_bundle` / `commit_bundle` | `load_extra_prompt` / `load_datasets` | `main()` combines with |
| --- | --- | --- | --- |
| fork | `tuple[str, list[str]]` | `tuple[str, list[str]]` | `[*a, *b, *c]` |
| upstream | `tuple[str, bool]` | `tuple[str, bool]` | `a or b or c` |

Some of the five conflict and some auto-merge, so a resolution can silently mix the two
conventions. Splatting a `bool` is a runtime `TypeError`.
Guarded by `skills/autoreview/tests/test_merge_invariants.py`.

**2. Deletion by replacement.** Six functions exist only in this fork, so taking upstream's
file wholesale removes them with no conflict marker: `resolve_commit_sha`,
`review_target_binding`, `enforce_review_expectations`, `canonical_json`, `_jcs_serialize`,
`sha256_hex`. Same guard file.

## Invariant: the interpreter guard must not move

`find_command`, `first_executable_candidate`, `is_within`, and `has_directory_component`
implement autoreview's refusal to execute any interpreter located inside the repository
under review. They are **byte-identical across merge-base, upstream, and fork** — verified
`sha256` prefix `5b3d5b7497fc217c`:

    for ref in "$(git merge-base upstream/main HEAD)" upstream/main HEAD; do
      git show "$ref:skills/autoreview/scripts/autoreview" \
        | awk '/^def (find_command|first_executable_candidate|is_within|has_directory_component)/,/^$/' \
        | shasum -a 256 | cut -c1-16
    done

Any post-merge difference there is a defect, not a resolution.

Practical consequence: `scripts/run-checks` must not hand autoreview an in-repo interpreter.
The repo's own `.venv/` is refused by design, so the script uses `python3` from PATH and
falls back to `.venv` only for the two steps that import PyYAML.

## Gates

`scripts/run-checks` mirrors `.github/workflows/validate.yml` step for step. The
`python tests` module list must stay byte-identical between the two. Both currently run:

- `skills/autoreview/scripts/autoreview_test.py`
- `skills.autoreview.tests.test_autoreview_hardening`
- `skills.autoreview.tests.test_receipt_contract`
- `skills.autoreview.tests.test_merge_invariants`

`test_receipt_contract` (32 tests) defends the fork's receipt feature. It was green but
executed by nothing until 2026-08-02; it is the specification to re-apply the receipt layer
against if `skills/autoreview/scripts/autoreview` is ever resolved as an ownership transfer.

`rerere.enabled` is set locally, so an abandoned merge attempt does not cost the resolutions
a second time.

## Lane constraint

This machine enforces a main-only lane via a PreToolUse hook. Verified by attempt:

- `git merge upstream/main` — denied by the hook (merge commit on shared main)
- `git rebase upstream/main` — denied by the hook (non-`origin/main` base)
- `git merge --ff-only upstream/main` — refused by git; histories have genuinely diverged

Only merge advances the merge base; cherry-picking mints new SHAs and would leave the base
frozen at `4664d27` while re-litigating the autoreview collision once per commit. So a real
sync needs the repository owner to authorize one merge commit explicitly. That authorization
has **not** been given as of this writing, and no sync has been performed.
