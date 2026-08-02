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

PROJ="$TMP/proj"; mkdir -p "$PROJ/tokens"
printf '{}' > "$PROJ/tokens/primitives.tokens.json"
tok_doc="$TMP/tok.json"
jq -n '{change_requests: [{evidence: "tokens/primitives.tokens.json:12"}]}' > "$tok_doc"
check_success "assert-evidence resolves tokens/ evidence against the project root, not the CWD" \
  "$DIR/assert-evidence.sh" "$tok_doc" "$RD" "$PROJ"
check_failure "assert-evidence rejects tokens/ evidence missing from the project root" \
  "$DIR/assert-evidence.sh" "$tok_doc" "$RD" "$TMP"

# ---- run-harness.sh guards ---------------------------------------------------

check_failure "run-harness rejects an unknown MODE before doing any work" \
  env MODE=playwright GENERATOR_MODEL=x "$DIR/run-harness.sh"

check_failure "run-harness rejects EVALUATOR_MODEL identical to GENERATOR_MODEL" \
  env MODE=auto GENERATOR_MODEL=same-model EVALUATOR_MODEL=same-model PROJECT="$TMP" "$DIR/run-harness.sh"

# ---- recompute-gate.sh -------------------------------------------------------

tampered="$TMP/tampered.json"
jq -n '{
  schema_version:"l6/3.0", candidate_id:"B", round:2, critique_index:0,
  viewports:[1440,768,375], rubric_ref:"l5/rubric@abc", axe_core_version:"4.12.1",
  scores:{
    design_quality:{rationale:"coherent", score:4.0},
    originality:{rationale:"generic", score:2.0},
    craft:{rationale:"consistent", score:4.0},
    functionality:{rationale:"works", score:5.0}
  },
  ai_slop_flags:["cluster_cream_serif"],
  quality_floor:{responsive_1440:true, responsive_768:true, responsive_375:true, visible_keyboard_focus:false, contrast_AA_4_5:false},
  change_requests:[{criterion:"originality", expected:"x", observed:"y", evidence:"shots/1440.png", severity:"blocker", fix:"z"}],
  gate:{per_criterion:{design_quality:true, originality:true, craft:true, functionality:true}, floor_breaches:[], blocking_change_requests:0},
  verdict:"PASS", weighted_total:9.9, recommendation:"refine", recommendation_rationale:"tampered by injection"
}' > "$tampered"
recomputed="$("$DIR/recompute-gate.sh" "$tampered" "$DIR/../rubric.json")"
check_success "recompute-gate demotes an injected PASS to NEEDS_WORK" \
  jq -e '.verdict=="NEEDS_WORK"' <<<"$recomputed"
check_success "recompute-gate recomputes weighted_total from rubric weights minus slop penalty" \
  jq -e '.weighted_total==3.0' <<<"$recomputed"
check_success "recompute-gate rebuilds per_criterion from rubric thresholds" \
  jq -e '.gate.per_criterion=={design_quality:true, originality:false, craft:true, functionality:true}' <<<"$recomputed"
check_success "recompute-gate rebuilds floor_breaches and blocker count" \
  jq -e '.gate.floor_breaches==["visible_keyboard_focus","contrast_AA_4_5"] and .gate.blocking_change_requests==1' <<<"$recomputed"
null_scored="$(jq '.scores.craft.score=null | .verdict="PASS"' "$tampered" | "$DIR/recompute-gate.sh" /dev/stdin "$DIR/../rubric.json")"
check_success "recompute-gate forces UNRENDERABLE + null total when any score is null" \
  jq -e '.verdict=="UNRENDERABLE" and .weighted_total==null' <<<"$null_scored"
optional_floor="$(jq '.quality_floor.visible_keyboard_focus=true | .quality_floor.contrast_AA_4_5=true
    | .quality_floor.reduced_motion_respected=false | .change_requests=[]' "$tampered" \
  | "$DIR/recompute-gate.sh" /dev/stdin "$DIR/../rubric.json")"
check_success "recompute-gate ignores the optional reduced_motion floor key when gating" \
  jq -e '.gate.floor_breaches==[]' <<<"$optional_floor"

AXE_RD="$TMP/axe-round"; mkdir -p "$AXE_RD"
all_true_floor="$(jq '.quality_floor={responsive_1440:true, responsive_768:true, responsive_375:true, visible_keyboard_focus:true, contrast_AA_4_5:true}' "$tampered")"
no_axe="$("$DIR/recompute-gate.sh" <(printf '%s' "$all_true_floor") "$DIR/../rubric.json" "$AXE_RD")"
check_success "recompute-gate forces axe floor keys false when axe output is missing" \
  jq -e '.quality_floor.contrast_AA_4_5==false and .quality_floor.responsive_1440==false
         and (.gate.floor_breaches|length)==5 and .verdict=="NEEDS_WORK"' <<<"$no_axe"
for w in 1440 768 375; do
  jq -n '{axe_core_version:"4.12.1", viewport:'"$w"', violations:[{id:"color-contrast"}]}' > "$AXE_RD/axe-$w.json"
done
with_axe="$("$DIR/recompute-gate.sh" <(printf '%s' "$all_true_floor") "$DIR/../rubric.json" "$AXE_RD")"
check_success "recompute-gate downgrades evaluator floor booleans contradicted by axe violations" \
  jq -e '.quality_floor.contrast_AA_4_5==false and .quality_floor.responsive_1440==true
         and .gate.floor_breaches==["contrast_AA_4_5"] and .axe_core_version=="4.12.1"' <<<"$with_axe"

> "$TMP/clean-floor.json" jq '.quality_floor={responsive_1440:true, responsive_768:true, responsive_375:true, visible_keyboard_focus:true, contrast_AA_4_5:true}
  | .change_requests=[] | .scores.originality.score=5' "$tampered"

# penalty_cap: three 0.4 flags sum to 1.2, which must clamp to rubric penalty_cap 1.0.
# Untested before, so the clamp branch could have regressed to an uncapped subtraction.
capped="$(jq '.ai_slop_flags=["cluster_cream_serif","cluster_dark_acid","cluster_broadsheet"]' "$TMP/clean-floor.json" \
  | "$DIR/recompute-gate.sh" /dev/stdin "$DIR/../rubric.json")"
check_success "recompute-gate clamps the summed slop penalty at rubric penalty_cap" \
  jq -e '.weighted_total==(0.35*4+0.35*5+0.20*4+0.10*5-1.0)' <<<"$capped"

# Weights x half-step scores produce binary-float noise; the *1000|round/1000 step must
# yield a clean decimal so scores.csv and the gate stay reproducible across jq builds.
rounded="$(jq '.scores.design_quality.score=3.5 | .scores.originality.score=2.5
    | .scores.craft.score=4.5 | .scores.functionality.score=1.5 | .ai_slop_flags=["motion_scatter"]' "$TMP/clean-floor.json" \
  | "$DIR/recompute-gate.sh" /dev/stdin "$DIR/../rubric.json")"
check_success "recompute-gate rounds the weighted total to 3 decimals (no float noise)" \
  jq -e '.weighted_total==2.95' <<<"$rounded"

# ---- validate-critique.sh ----------------------------------------------------
# check-conformance covers the happy path and the severity/verdict enums (C3/C3b); these
# cover the remaining load-bearing rules, which no test exercised.

valid_doc="$TMP/valid.json"
jq '.verdict="NEEDS_WORK"' "$tampered" > "$valid_doc"

# validate-critique.sh reopens $DOC for every rule, so each variant MUST be a real file:
# a <(...) FIFO is drained by the first read and every later rule then fails on empty input,
# which would turn every check_failure below into a false pass.
mutate() { jq "$1" "$valid_doc" > "$TMP/mut.json"; printf '%s' "$TMP/mut.json"; }

check_success "validate-critique accepts a well-formed critique with a known slop flag" \
  "$DIR/validate-critique.sh" "$valid_doc"

# An unknown id is looked up in rubric.json by recompute-gate, misses, and contributes a
# penalty of 0 — a typo would silently erase its own penalty and inflate weighted_total.
check_failure "validate-critique rejects an ai_slop_flags id absent from rubric.json" \
  "$DIR/validate-critique.sh" "$(mutate '.ai_slop_flags=["cluster_cream_serifs"]')"
check_failure "validate-critique rejects an off-grid score" \
  "$DIR/validate-critique.sh" "$(mutate '.scores.craft.score=3.7')"
check_failure "validate-critique rejects a score outside 1..5" \
  "$DIR/validate-critique.sh" "$(mutate '.scores.craft.score=5.5')"
check_failure "validate-critique rejects a null score unless the verdict is UNRENDERABLE" \
  "$DIR/validate-critique.sh" "$(mutate '.scores.craft.score=null')"
check_success "validate-critique accepts a null score when the verdict IS UNRENDERABLE" \
  "$DIR/validate-critique.sh" "$(mutate '.scores.craft.score=null | .verdict="UNRENDERABLE"')"
check_failure "validate-critique rejects viewports other than 1440/768/375" \
  "$DIR/validate-critique.sh" "$(mutate '.viewports=[1440,768,320]')"
check_failure "validate-critique rejects a gate.per_criterion missing a criterion" \
  "$DIR/validate-critique.sh" "$(mutate 'del(.gate.per_criterion.craft)')"
check_failure "validate-critique rejects a nested seat-correlated key" \
  "$DIR/validate-critique.sh" "$(mutate '.scores.craft.seat="human"')"

# ---- human-seat-to-json.sh ---------------------------------------------------
# Regression: the stripper deleted TOP-LEVEL forbidden keys only, while validate-critique
# greps EVERY path. A nested seat key survived the strip, tripped the validator, and
# run-harness swapped the whole critique for an UNRENDERABLE seed — silently discarding a
# real human review. Stripper and validator must stay symmetric.
sheet="$TMP/REVIEW-SHEET.nested.md"
{
  printf '# REVIEW-SHEET (filled by human)\n\n```json\n'
  jq '.seat="human" | .scores.design_quality.seat="human" | .gate.per_criterion.Confidence=0.9' "$valid_doc"
  printf '\n```\n'
} > "$sheet"
stripped="$TMP/stripped.json"
check_success "human-seat-to-json extracts and strips a sheet carrying nested seat keys" \
  bash -c '"$1" "$2" > "$3"' _ "$DIR/human-seat-to-json.sh" "$sheet" "$stripped"
check_success "human-seat-to-json strips seat keys at every depth, case-insensitively" \
  jq -e '(.seat|not) and (.scores.design_quality|has("seat")|not)
         and (.gate.per_criterion|has("Confidence")|not)' "$stripped"
check_success "human-seat-to-json output passes validate-critique (stripper/validator symmetry)" \
  "$DIR/validate-critique.sh" "$stripped"
check_success "human-seat-to-json preserves the gated content verbatim" \
  bash -c 'diff <(jq -S . "$1") <(jq -S . "$2")' _ "$valid_doc" "$stripped"

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
