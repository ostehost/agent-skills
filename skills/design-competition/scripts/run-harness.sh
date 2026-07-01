#!/usr/bin/env bash
# Generator-evaluator (GAN-style) harness loop. Minimal SDK-less fallback wrapper.
set -euo pipefail

MODE="${MODE:-auto}"              # auto | human  (the ONLY mode branch: which evaluator to invoke)
PROJECT="${PROJECT:-$PWD}"
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
MAX_ROUNDS="${MAX_ROUNDS:-12}"    # range 5-15 [V]; ceiling >15 unverified
MAX_BUDGET_USD="${MAX_BUDGET_USD:-25}"
PORT="${PORT:-4173}"
CID="${CID:-main}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$(git -C "$PROJECT" rev-parse --short HEAD)-001"
RUN="$PROJECT/runs/$RUN_ID"
CAND="$RUN/candidates/$CID"
SCHEMA="$SKILL_DIR/schemas/critique.schema.json"
mkdir -p "$CAND"
cp "$SKILL_DIR/templates/NEXT_FINDINGS.json" "$RUN/NEXT_FINDINGS.json"
echo 0 > "$RUN/budgets.json.spent"

log(){ printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >> "$RUN/events.jsonl"; }

sum_budget(){ # add a ResultMessage total_cost_usd to the running total (X: no cumulative field)
  local add="$1" cur; cur=$(cat "$RUN/budgets.json.spent"); awk -v a="$cur" -v b="$add" 'BEGIN{print a+b}' > "$RUN/budgets.json.spent"; }

budget_ok(){ awk -v s="$(cat "$RUN/budgets.json.spent")" -v m="$MAX_BUDGET_USD" 'BEGIN{exit !(s<m)}'; }

# Portable critique validator: prefer ajv (full JSON Schema), else fall back to validate-critique.sh (jq).
validate_json(){ # $1=schema $2=doc
  if command -v ajv >/dev/null 2>&1; then ajv validate --spec=draft2020 -s "$1" -d "$2" 2>>"$RUN/events.jsonl"
  else "$SKILL_DIR/scripts/validate-critique.sh" "$2" "$1" 2>>"$RUN/events.jsonl"; fi; }

stop(){ echo "$1" > "$RUN/STOP_REASON"; log "STOP $1"; git -C "$PROJECT" add -A && git -C "$PROJECT" commit -q -m "harness: stop $1 ($RUN_ID)" || true; exit 0; }

for ((n=0; n<MAX_ROUNDS; n++)); do
  RD="$CAND/round-$n"; mkdir -p "$RD/build" "$RD/shots"
  [ -f "$RUN/AGENT_STOP" ] && stop operator_halt
  budget_ok || stop budget

  # --- STEER injection (read+inject+clear in wrapper) ---
  STEER=""; [ -f "$RUN/STEER.md" ] && { STEER=$(cat "$RUN/STEER.md"); : > "$RUN/STEER.md"; }

  # --- GENERATOR (reads exactly one baton: NEXT_FINDINGS.json) ---
  log "round $n generate"
  claude --agent generator \
    -p "Read $RUN/NEXT_FINDINGS.json (the baton — the single CURRENT critique, not a transcript),
        DESIGN.md, BRIEF.yaml, tokens/, and $RUN/scores.csv (the running trend, if present). $STEER
        Two-pass plan-then-build into $RD/build. You decide refine|pivot from the scores.csv trend." \
    --output-format json > "$RD/gen.result.json" || true
  sum_budget "$(jq -r '.total_cost_usd // 0' "$RD/gen.result.json")"

  # --- SHARED PINNED CAPTURE (invariant 3 / S4): NOT a seat ---
  if ! "$SKILL_DIR/scripts/capture-shots.sh" "http://localhost:$PORT" "$RD/shots"; then
    log "round $n capture failed -> UNRENDERABLE"
  fi

  # --- EVALUATOR (the ONLY mode branch: pick which seat to invoke) ---
  K=0; OUT="$RD/critique-$K.json"; AUDIT="$RD/critique-$K.audit.json"
  if [ "$MODE" = "auto" ]; then
    claude --agent evaluator \
      --mcp-config "$RD/mcp.json" --strict-mcp-config \
      --allowedTools "mcp__playwright__*" \
      -p "Evaluate http://localhost:$PORT. Use shots/ at $RD/shots (already captured). Emit L6 JSON. NO seat field." \
      --output-format json > "$RD/eval.result.json" || true
    sum_budget "$(jq -r '.total_cost_usd // 0' "$RD/eval.result.json")"
    jq '.structured_output // .result | fromjson? // .' "$RD/eval.result.json" > "$OUT"
  else
    # human seat: wrapper converts the filled REVIEW-SHEET form to the same JSON path
    "$SKILL_DIR/scripts/human-seat-to-json.sh" "$RD/REVIEW-SHEET.filled.md" > "$OUT"
  fi

  # --- WRAPPER: validate schema + evidence, recompute gate deterministically (R-INJECTION defense) ---
  if [ ! -s "$OUT" ] || ! validate_json "$SCHEMA" "$OUT"; then
    log "round $n invalid critique -> UNRENDERABLE seed"; jq '.verdict="UNRENDERABLE"' "$SKILL_DIR/templates/NEXT_FINDINGS.json" > "$OUT"
  fi
  "$SKILL_DIR/scripts/assert-evidence.sh" "$OUT" "$RD" || stop error   # evidence files must exist on disk
  # sidecar provenance (loop-blind): wrapper records seat + any auto-only stats here, never in $OUT
  jq -n --arg seat "$MODE" '{evaluator:{type:$seat}}' > "$AUDIT"

  # --- BATON: merge round critiques -> merged.json -> NEXT_FINDINGS.json ---
  cp "$OUT" "$RD/merged.json"            # single-critique round; hybrid rounds run merge() here
  cp "$RD/merged.json" "$RUN/NEXT_FINDINGS.json"
  "$SKILL_DIR/scripts/render-baton-md.sh" "$RUN/NEXT_FINDINGS.json" > "$RUN/NEXT_FINDINGS.md" || true

  VERDICT=$(jq -r '.verdict' "$RUN/NEXT_FINDINGS.json")
  jq -r '[.candidate_id,.round,.verdict,(.weighted_total//"")]|@csv' "$RUN/NEXT_FINDINGS.json" >> "$RUN/scores.csv"
  log "round $n verdict=$VERDICT (no stop-on-PASS; C8)"

  # --- per-round commit (authoritative; Stop hook is only a crash backstop) ---
  git -C "$PROJECT" add -A && git -C "$PROJECT" commit -q -m "round $n $VERDICT ($RUN_ID)" || true
  # NOTE: PASS is recorded, NOT terminal. Loop continues to MAX_ROUNDS / budget / plateau (L7).
done
stop iter_cap
