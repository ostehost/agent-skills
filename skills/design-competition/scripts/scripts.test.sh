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
