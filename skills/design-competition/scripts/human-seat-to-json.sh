#!/usr/bin/env bash
# Convert a filled human REVIEW-SHEET into the IDENTICAL L6 gated artifact the auto seat emits.
# This is the swappable-seat bridge: after this runs, the loop CANNOT tell which seat produced
# the JSON (invariant 1). The human's filled form is expected to embed a fenced ```json block
# carrying the gated fields; this script extracts it, drops any stray seat-correlated keys, and
# re-serializes with jq so byte layout matches the auto path (both go through `jq .`).
set -euo pipefail
FORM="${1:?filled review sheet}"
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
DIR="$SKILL_DIR"
# extract the first fenced json block
BLK="$(awk '/^```json$/{f=1;next} /^```$/{f=0} f' "$FORM")"
[ -n "$BLK" ] || { echo "human-seat-to-json: no \`\`\`json block in $FORM" >&2; exit 1; }
# Strip any seat-correlated key AT ANY DEPTH, then canonicalize via jq so byte layout matches the
# auto path. The strip list is SINGLE-SOURCED from schemas/forbidden-keys.txt (M2 — previously 11
# keys here vs 14 in validate-critique.sh, so a human form carrying self_preference/
# generator_model_family/method passed the stripper then failed validation).
# The strip must match validate-critique.sh's DETECTION, which greps every path case-insensitively.
# A top-level-only `del(.k1,.k2,...)` did not: a nested key (e.g. scores.design_quality.seat)
# survived the stripper, then tripped the validator, and run-harness replaced the whole critique
# with an UNRENDERABLE seed — silently discarding a real human review. walk + case-insensitive
# match keeps stripper and validator symmetric.
FK_JSON="$(grep -vE '^[[:space:]]*#|^[[:space:]]*$' "$DIR/schemas/forbidden-keys.txt" \
  | jq -R 'ascii_downcase' | jq -sc .)"
[ "$FK_JSON" != "[]" ] || { echo "human-seat-to-json: empty/absent schemas/forbidden-keys.txt" >&2; exit 1; }
printf '%s' "$BLK" | jq --argjson fk "$FK_JSON" '
  walk(if type == "object"
       then with_entries(select(((.key | ascii_downcase) as $k | $fk | index($k)) == null))
       else . end)'
