#!/usr/bin/env bash
# CONFORMANCE CHECK for the shared contracts (run via `just check-conformance`).
# Proves, against the ACTUAL files (not prose):
#   C1  Schema is seat-blind by construction: additionalProperties:false at every object
#       level AND no seat-correlated key is declared anywhere in schemas/critique.schema.json.
#   C2  SWAPPABLE SEAT / byte-identity: an auto-emitted critique and a human-emitted critique
#       carrying identical gated content serialize to BYTE-IDENTICAL critique-<k>.json.
#   C3  Both emitted critiques validate against the schema (ajv if present, else jq fallback).
#   C4  SHARED BATON single read path: the loop reads ONLY NEXT_FINDINGS.json as the baton, never
#       the sidecar, the .md mirror, or the deprecated FINDINGS.md.
#   C5  VIEWPORTS pinned to 1440/768/375 in both capture-shots.sh and the schema.
#   C6  RUBRIC weight DIRECTION asserted (design+originality > craft+functionality) and numbers
#       labeled unverified.
set -euo pipefail
P="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
S="$P/scripts"
SCHEMA="$P/schemas/critique.schema.json"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
pass(){ printf 'PASS  %s\n' "$1"; }
die(){ printf 'FAIL  %s\n' "$1" >&2; exit 1; }

# ---- C1 seat-blind schema ----------------------------------------------------
# Every object level closed, INCLUDING gate.per_criterion (M2: was the open seat channel).
jq -e '.additionalProperties==false and .properties.scores.additionalProperties==false and .properties.gate.additionalProperties==false and .properties.gate.properties.per_criterion.additionalProperties==false and .["$defs"].scoreObj.additionalProperties==false and .["$defs"].changeRequest.additionalProperties==false' "$SCHEMA" >/dev/null \
  || die "C1 schema not closed (additionalProperties must be false on every object, incl. gate.per_criterion)"
# Single source of truth for the forbidden seat-key list (M2): schemas/forbidden-keys.txt.
FORBIDDEN_FILE="$P/schemas/forbidden-keys.txt"
[ -f "$FORBIDDEN_FILE" ] || die "C1 missing $FORBIDDEN_FILE (single-source forbidden-key list)"
# quoted-property alternation so we catch a DECLARED property, not prose in $comment/description
qpat=$(grep -vE '^[[:space:]]*#|^[[:space:]]*$' "$FORBIDDEN_FILE" | sed 's/.*/"&"[[:space:]]*:/' | paste -sd'|' -)
if grep -Eq "$qpat" "$SCHEMA"; then die "C1 seat-correlated key DECLARED as a property in gated schema"; fi
pass "C1 schema is seat-blind (all objects closed incl. per_criterion; no seat-correlated property; list single-sourced)"

# ---- shared gated content used by BOTH seats --------------------------------
GATED='{
  "schema_version":"l6/3.0","candidate_id":"B","round":2,"critique_index":0,
  "viewports":[1440,768,375],"rubric_ref":"l5/rubric@abc","axe_core_version":"4.12.1",
  "scores":{
    "design_quality":{"rationale":"coherent whole at all three widths","score":4.0},
    "originality":{"rationale":"palette is a generic terracotta default","score":2.0},
    "craft":{"rationale":"spacing rhythm consistent","score":4.0},
    "functionality":{"rationale":"primary job works, keyboard reachable","score":5.0}
  },
  "ai_slop_flags":["cluster_cream_serif"],
  "quality_floor":{"responsive_1440":true,"responsive_768":true,"responsive_375":true,"visible_keyboard_focus":false,"contrast_AA_4_5":false},
  "change_requests":[
    {"criterion":"originality","type":"aesthetic","expected":"brief-specific signature","observed":"generic terracotta palette","evidence":"shots/1440.png","severity":"blocker","fix":"replace palette"}
  ],
  "gate":{"per_criterion":{"design_quality":true,"originality":false,"craft":true,"functionality":true},"floor_breaches":["visible_keyboard_focus","contrast_AA_4_5"],"blocking_change_requests":1},
  "verdict":"NEEDS_WORK","weighted_total":3.0,"recommendation":"refine","recommendation_rationale":"fix floor + palette"
}'

# AUTO seat path: the SDK result file wraps the critique in .structured_output; the wrapper
# extracts it then jq-serializes, exactly as run-harness.sh does.
printf '%s' "$GATED" | jq '{structured_output: .}' > "$TMP/eval.result.json"
jq '.structured_output // .result | fromjson? // .' "$TMP/eval.result.json" \
  | jq . > "$TMP/critique-auto.json"

# HUMAN seat path: a filled REVIEW-SHEET embedding the SAME gated json PLUS stray seat keys,
# routed through human-seat-to-json.sh (which strips seat keys + canonicalizes via jq).
{
  printf '# REVIEW-SHEET (filled by human)\n\n```json\n'
  printf '%s' "$GATED" | jq '. + {seat:"human", confidence:0.9, samples:[3,4]}'
  printf '\n```\n'
} > "$TMP/REVIEW-SHEET.filled.md"
"$S/human-seat-to-json.sh" "$TMP/REVIEW-SHEET.filled.md" | jq . > "$TMP/critique-human.json"

# ---- C2 byte-identity --------------------------------------------------------
cmp -s "$TMP/critique-auto.json" "$TMP/critique-human.json" \
  || { diff "$TMP/critique-auto.json" "$TMP/critique-human.json" >&2 || true; die "C2 auto vs human critique NOT byte-identical"; }
pass "C2 auto-emitted and human-emitted critique-<k>.json are byte-identical (NOTE: staged fixture — proves wrapper canonicalization determinism, NOT live-seat byte-identity; see HARNESS §1/§17)"

# ---- C2b adversarial seat-channel regression (review probes adv1/adv2/adv2b) -
# Honest about which validator catches what. Free-text watermarks (adv1) are NOT policeable by either.
adv2b=$(printf '%s' "$GATED" | jq '.gate.per_criterion.seat = 7')         # literal forbidden key
if "$S/validate-critique.sh" <(printf '%s' "$adv2b") "$SCHEMA" >/dev/null 2>&1; then
  die "C2b jq validator ACCEPTED a forbidden 'seat' key inside per_criterion"
fi
if command -v ajv >/dev/null 2>&1; then
  adv2=$(printf '%s' "$GATED" | jq '.gate.per_criterion.x_seatchan = 7')   # novel (non-listed) key
  printf '%s' "$adv2" > "$TMP/adv2.json"
  ajv validate --spec=draft2020 -s "$SCHEMA" -d "$TMP/adv2.json" >/dev/null 2>&1 \
    && die "C2b schema ACCEPTED a novel key in per_criterion (structural seat channel still open)" || true
  pass "C2b seat channels closed: jq rejects named keys; ajv rejects novel keys in per_criterion"
else
  pass "C2b jq rejects named seat keys in per_criterion (install ajv to also prove novel-key closure; free-text watermarks remain unpoliceable by design)"
fi

# ---- C3 both validate --------------------------------------------------------
if command -v ajv >/dev/null 2>&1; then
  ajv validate --spec=draft2020 -s "$SCHEMA" -d "$TMP/critique-auto.json"  >/dev/null || die "C3 auto fails schema (ajv)"
  ajv validate --spec=draft2020 -s "$SCHEMA" -d "$TMP/critique-human.json" >/dev/null || die "C3 human fails schema (ajv)"
  pass "C3 both critiques validate against the schema (ajv)"
else
  "$S/validate-critique.sh" "$TMP/critique-auto.json"  "$SCHEMA" >/dev/null || die "C3 auto fails schema (jq fallback)"
  "$S/validate-critique.sh" "$TMP/critique-human.json" "$SCHEMA" >/dev/null || die "C3 human fails schema (jq fallback)"
  pass "C3 both critiques validate against the schema (jq fallback; install ajv for full draft-2020-12)"
fi

# ---- C4 single baton read path ----------------------------------------------
grep -q 'NEXT_FINDINGS.json (the baton' "$S/run-harness.sh" || die "C4 generator does not read NEXT_FINDINGS.json as baton"
# the generator prompt block must NOT read the sidecar, the md mirror, or deprecated FINDINGS.md
genblock="$(awk '/GENERATOR \(reads exactly one baton/{f=1} f&&/output-format json/{print;f=0} f' "$S/run-harness.sh")"
printf '%s' "$genblock" | grep -Eq 'audit.json|NEXT_FINDINGS.md|FINDINGS\.md' && die "C4 generator reads a non-baton feedback file"
pass "C4 single FEEDBACK baton = NEXT_FINDINGS.json (generator also reads DESIGN/BRIEF/tokens/scores.csv, but no sidecar/.md/FINDINGS.md feedback)"

# ---- C5 viewports pinned -----------------------------------------------------
grep -q '\[1440,900\],\[768,1024\],\[375,812\]' "$S/capture-shots.sh" || die "C5 capture viewports not pinned 1440/768/375"
jq -e '.properties.viewports.items.enum==[1440,768,375]' "$SCHEMA" >/dev/null || die "C5 schema viewports enum mismatch"
pass "C5 viewports pinned to 1440/768/375 in capture + schema"

# ---- C6 rubric weight direction ---------------------------------------------
jq -e '.weight_direction.verified==true and (.weight_direction.assert|test("design_quality.*originality.*>.*craft.*functionality"))' "$P/rubric.json" >/dev/null \
  || die "C6 rubric weight DIRECTION not asserted"
dq=$(jq '.criteria[]|select(.id=="design_quality").weight' "$P/rubric.json")
or=$(jq '.criteria[]|select(.id=="originality").weight' "$P/rubric.json")
cr=$(jq '.criteria[]|select(.id=="craft").weight' "$P/rubric.json")
fn=$(jq '.criteria[]|select(.id=="functionality").weight' "$P/rubric.json")
awk -v a="$dq" -v b="$or" -v c="$cr" -v d="$fn" 'BEGIN{exit !((a+b)>(c+d))}' || die "C6 numeric weights violate the verified direction"
jq -e '._unverified|test("UNVERIFIED")' "$P/rubric.json" >/dev/null || die "C6 rubric numbers not labeled unverified"
pass "C6 rubric encodes verified DIRECTION; numbers labeled unverified"

echo "ALL CONFORMANCE CHECKS PASSED"
