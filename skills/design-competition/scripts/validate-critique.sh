#!/usr/bin/env bash
# Portable jq-only fallback validator for the L6 gated critique artifact.
# Prefer `ajv validate -s schemas/critique.schema.json -d <doc>` when ajv is installed;
# this exists so the harness is runnable on a stock box (jq only). It enforces the
# load-bearing parts of schemas/critique.schema.json: seat-blindness (no forbidden keys),
# the four criteria, the 0.5 score grid in 1..5 (or null), and the verdict/severity enums.
set -euo pipefail
DOC="${1:?critique json}"; SCHEMA="${2:-}"   # SCHEMA arg accepted for ajv-compatible call shape; unused here
DIR="$(cd "$(dirname "$0")/.." && pwd)"
# NOTE: ajv against schemas/critique.schema.json is AUTHORITATIVE. This jq fallback enforces only the
# load-bearing subset (it does NOT implement additionalProperties:false, enums, or types) so the harness
# runs on a stock box. Seat-blindness here is the NAMED-KEY defense; structural closure needs ajv.

fail(){ echo "validate-critique: $1" >&2; exit 1; }

jq -e . "$DOC" >/dev/null 2>&1 || fail "not valid JSON: $DOC"

# 1. seat-blindness: NO seat-correlated key anywhere in the gated artifact (invariant 1).
#    Forbidden list is SINGLE-SOURCED from schemas/forbidden-keys.txt (M2 — was drifting across 3 files).
FORBIDDEN="$(grep -vE '^[[:space:]]*#|^[[:space:]]*$' "$DIR/schemas/forbidden-keys.txt" | paste -sd'|' -)"
[ -n "$FORBIDDEN" ] || fail "empty/absent schemas/forbidden-keys.txt"
if jq -r 'paths|map(tostring)|join(".")' "$DOC" | grep -Eiq "(^|\.)(${FORBIDDEN})(\.|$)"; then
  jq -r 'paths|map(tostring)|join(".")' "$DOC" | grep -Ei "(^|\.)(${FORBIDDEN})(\.|$)" >&2
  fail "forbidden seat-correlated key present (must live in critique-<k>.audit.json sidecar)"
fi

# 2. required top-level keys + const schema_version
req='["schema_version","candidate_id","round","critique_index","viewports","rubric_ref","axe_core_version","scores","ai_slop_flags","quality_floor","change_requests","gate","verdict","weighted_total","recommendation"]'
jq -e --argjson r "$req" 'all($r[]; . as $k | ($k|in(.))) // ([keys] as $x | ($r - ($x[0]))|length==0)' "$DOC" >/dev/null 2>&1 \
  || jq -e --argjson r "$req" '($r - (keys))|length==0' "$DOC" >/dev/null || fail "missing required top-level key(s)"
jq -e '.schema_version=="l6/3.0"' "$DOC" >/dev/null || fail "schema_version must be l6/3.0"

# 3. verdict enum
jq -e '.verdict as $v | ["PASS","NEEDS_WORK","UNRENDERABLE"]|index($v)' "$DOC" >/dev/null || fail "bad verdict enum"

# 4. four criteria present, each {rationale,score}; score null OR on 0.5 grid in [1,5]
for c in design_quality originality craft functionality; do
  jq -e --arg c "$c" '.scores[$c]|has("rationale") and has("score")' "$DOC" >/dev/null || fail "scores.$c missing rationale/score"
  jq -e --arg c "$c" '.scores[$c].score as $s | ($s==null) or ($s>=1 and $s<=5 and (($s*2)|floor)==($s*2))' "$DOC" >/dev/null \
    || fail "scores.$c.score off the 0.5 grid / out of 1..5"
done

# 5. null scores ONLY allowed when verdict==UNRENDERABLE
if jq -e '.verdict!="UNRENDERABLE" and ([.scores[].score]|any(.==null))' "$DOC" >/dev/null; then
  fail "null score with verdict != UNRENDERABLE"
fi

# 6. change_request severities + criteria enums
jq -e '[.change_requests[]?.severity]|all(["blocker","major","medium","nitpick"]|index(.)!=null)' "$DOC" >/dev/null || fail "bad change_request severity"
jq -e '[.change_requests[]?.criterion]|all(["design_quality","originality","craft","functionality"]|index(.)!=null)' "$DOC" >/dev/null || fail "bad change_request criterion"

# 7. viewports pinned to exactly [1440,768,375] (order-free)
jq -e '(.viewports|sort)==( [375,768,1440] )' "$DOC" >/dev/null || fail "viewports must be 1440/768/375"

# 8. gate.per_criterion keys
for c in design_quality originality craft functionality; do
  jq -e --arg c "$c" '.gate.per_criterion | has($c)' "$DOC" >/dev/null || fail "gate.per_criterion.$c missing"
  jq -e --arg c "$c" '.gate.per_criterion[$c] | type == "boolean"' "$DOC" >/dev/null || fail "gate.per_criterion.$c must be boolean"
done

echo "ok: $DOC"
