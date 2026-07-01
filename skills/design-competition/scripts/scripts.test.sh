#!/usr/bin/env bash
# Fast, dependency-free unit tests for the pure jq/bash transforms in this
# skill's scripts/ that check-conformance.sh doesn't already exercise
# end-to-end (validate-critique.sh and human-seat-to-json.sh are covered
# there, via real fixtures). Run directly: scripts/scripts.test.sh
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
fail=0

check_success() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then
    printf 'ok - %s\n' "$desc"
  else
    printf 'FAIL - %s\n' "$desc" >&2
    fail=1
  fi
}

check_failure() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then
    printf 'FAIL - %s (expected a nonzero exit)\n' "$desc" >&2
    fail=1
  else
    printf 'ok - %s\n' "$desc"
  fi
}

check_contains() {
  local desc="$1" haystack="$2" needle="$3"
  if [[ "$haystack" == *"$needle"* ]]; then
    printf 'ok - %s\n' "$desc"
  else
    printf 'FAIL - %s (missing %q)\n' "$desc" "$needle" >&2
    fail=1
  fi
}

# ---- assert-evidence.sh ------------------------------------------------------

RD="$TMP/round"; mkdir -p "$RD/shots"
printf 'fake png' > "$RD/shots/1440.png"

good_doc="$TMP/good.json"
jq -n '{change_requests: [{evidence: "shots/1440.png"}, {evidence: "axe:color-contrast"}]}' > "$good_doc"
check_success "assert-evidence accepts an existing shots/ file plus runtime-oracle evidence" \
  "$DIR/assert-evidence.sh" "$good_doc" "$RD"

bad_doc="$TMP/bad.json"
jq -n '{change_requests: [{evidence: "shots/375.png"}]}' > "$bad_doc"
check_failure "assert-evidence rejects a missing shots/ file" \
  "$DIR/assert-evidence.sh" "$bad_doc" "$RD"

# ---- render-baton-md.sh -------------------------------------------------------

baton="$TMP/NEXT_FINDINGS.json"
jq -n '{
  verdict: "NEEDS_WORK",
  recommendation: "refine",
  change_requests: [
    {severity: "blocker", criterion: "originality", observed: "generic palette", evidence: "shots/1440.png", fix: "restyle"}
  ]
}' > "$baton"
md="$("$DIR/render-baton-md.sh" "$baton")"
check_contains "render-baton-md includes the verdict" "$md" 'verdict:** NEEDS_WORK'
check_contains "render-baton-md includes the change request line" "$md" \
  '[blocker] originality: generic palette (shots/1440.png) -> restyle'
check_contains "render-baton-md includes the recommendation" "$md" 'recommendation (advisory):** refine'
check_contains "render-baton-md never reads the loop baton itself" "$md" 'The loop NEVER reads this file'

empty_baton="$TMP/EMPTY.json"
jq -n '{verdict: "PASS", recommendation: "ship", change_requests: []}' > "$empty_baton"
empty_md="$("$DIR/render-baton-md.sh" "$empty_baton")"
check_contains "render-baton-md handles an empty change_requests array without crashing" "$empty_md" 'PASS'

if [ "$fail" -eq 0 ]; then
  echo "ALL SCRIPT UNIT TESTS PASSED"
else
  exit 1
fi
