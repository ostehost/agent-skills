#!/usr/bin/env bash
# R-INJECTION defense: deterministically recompute a validated critique's gate
# fields from rubric.json (and, when AXE_DIR is given, the pinned axe oracle's
# output), so a prompt-injected (or merely sloppy) evaluator can never award
# itself a PASS. Model-authored scores, rationales, slop flags, and
# change_requests are kept verbatim; everything derivable is overwritten:
#   - quality_floor (axe-sourced keys): AND-ed with the oracle evidence — a
#     missing axe-<w>.json forces that viewport's axe floor keys false (fail
#     closed), a present file downgrades keys contradicted by recorded
#     violations, and axe_core_version is stamped from the oracle output. The
#     evaluator can lower a floor key, never raise one past the oracle.
#   - gate.per_criterion (score >= rubric threshold), gate.floor_breaches
#     (required rubric floor keys only — optional house-rule keys like
#     reduced_motion_respected are advisory), gate.blocking_change_requests
#     (severity==blocker count), weighted_total (rubric weights minus capped
#     slop penalties; null if UNRENDERABLE), and verdict (UNRENDERABLE if
#     declared or any score is null; NEEDS_WORK on any gate failure, floor
#     breach, or blocker; else PASS).
# Emits the recomputed critique on stdout.
set -euo pipefail
DOC="${1:?critique json}"; RUBRIC="${2:?rubric.json}"; AXE_DIR="${3:-}"

CRITIQUE="$(cat "$DOC")"

if [ -n "$AXE_DIR" ]; then
  for w in 1440 768 375; do
    axe_file="$AXE_DIR/axe-$w.json"
    if [ ! -f "$axe_file" ]; then
      CRITIQUE="$(jq ".quality_floor.responsive_$w=false
        | .quality_floor.visible_keyboard_focus=false
        | .quality_floor.contrast_AA_4_5=false" <<<"$CRITIQUE")"
    else
      # Downgrade-only merge: axe violations are machine facts the evaluator
      # cannot overrule upward. Focus-reachability rules approximate the
      # keyboard-focus floor (axe cannot fully verify focus VISIBILITY — the
      # floor is explicitly PARTIAL, see rubric _floor_note).
      CRITIQUE="$(jq --slurpfile axe "$axe_file" '
        ([$axe[0].violations[]?.id]) as $v
        | (if ($v | index("color-contrast")) != null then .quality_floor.contrast_AA_4_5 = false else . end)
        | (if ([$v[] | select(IN("focus-order-semantics","frame-focusable-content","scrollable-region-focusable","tabindex"))] | length) > 0
           then .quality_floor.visible_keyboard_focus = false else . end)
        | (if ($axe[0].axe_core_version | type) == "string" then .axe_core_version = $axe[0].axe_core_version else . end)
      ' <<<"$CRITIQUE")"
    fi
  done
fi

jq --slurpfile rubric "$RUBRIC" '
  $rubric[0] as $r
  | ($r.criteria | map({key: .id, value: .}) | from_entries) as $crit
  | ([.scores | to_entries[] | .value.score] | any(. == null)) as $has_null
  | ((.verdict == "UNRENDERABLE") or $has_null) as $unrenderable
  | .gate.per_criterion = ([
      .scores | to_entries[]
      | {key: .key, value: ((.value.score != null) and (.value.score >= ($crit[.key].threshold // 1)))}
    ] | from_entries)
  | ($r.quality_floor | map(.key)) as $floor_keys
  | .gate.floor_breaches = ([.quality_floor | to_entries[]
      | select(.value == false and (.key as $k | $floor_keys | index($k) != null)) | .key])
  | .gate.blocking_change_requests = ([.change_requests[]? | select(.severity == "blocker")] | length)
  | .weighted_total = (if $unrenderable then null else
      ((([.scores | to_entries[] | (($crit[.key].weight // 0) * .value.score)] | add)
        - ([.ai_slop_flags[]? as $f | ($r.slop_flags[] | select(.id == $f) | .penalty)] | add // 0
           | if . > ($r.penalty_cap // 1) then ($r.penalty_cap // 1) else . end))
       * 1000 | round / 1000)
    end)
  | .verdict = (if $unrenderable then "UNRENDERABLE"
      elif ((.gate.per_criterion | to_entries | any(.value == false))
            or ((.gate.floor_breaches | length) > 0)
            or (.gate.blocking_change_requests > 0))
      then "NEEDS_WORK"
      else "PASS" end)
' <<<"$CRITIQUE"
