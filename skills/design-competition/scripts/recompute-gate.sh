#!/usr/bin/env bash
# R-INJECTION defense: deterministically recompute a validated critique's gate
# fields from rubric.json, so a prompt-injected (or merely sloppy) evaluator can
# never award itself a PASS. Model-authored scores, rationales, floor booleans,
# slop flags, and change_requests are kept verbatim; everything derivable is
# overwritten: gate.per_criterion (score >= rubric threshold), gate.floor_breaches
# (false floor keys — only the rubric's required quality_floor keys gate; optional
# house-rule keys like reduced_motion_respected are advisory),
# gate.blocking_change_requests (severity==blocker count),
# weighted_total (rubric weights minus capped slop penalties; null if
# UNRENDERABLE), and verdict (UNRENDERABLE if declared or any score is null;
# NEEDS_WORK on any gate failure, floor breach, or blocker; else PASS).
# Emits the recomputed critique on stdout.
set -euo pipefail
DOC="${1:?critique json}"; RUBRIC="${2:?rubric.json}"

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
' "$DOC"
