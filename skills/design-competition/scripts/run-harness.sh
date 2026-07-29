#!/usr/bin/env bash
# Generator-evaluator (GAN-style) harness loop. Minimal SDK-less fallback wrapper.
set -euo pipefail

MODE="${MODE:-auto}"              # auto | human  (the ONLY mode branch: which evaluator to invoke)
case "$MODE" in
  auto|human) ;;
  *) echo "run-harness: MODE must be 'auto' or 'human' (got '$MODE')" >&2; exit 2 ;;
esac
PROJECT="${PROJECT:-$PWD}"
# Canonicalize: relative PROJECT (e.g. ".") would make RD/RUN relative, and the
# runs/<id>/live symlink target would then resolve relative to the link's parent
# — a broken link the server/capture would dutifully serve as an error page.
PROJECT="$(cd "$PROJECT" 2>/dev/null && pwd)" || { echo "run-harness: PROJECT dir not found: $PROJECT" >&2; exit 2; }
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
MAX_ROUNDS="${MAX_ROUNDS:-12}"    # range 5-15 [V]; ceiling >15 unverified
MAX_BUDGET_USD="${MAX_BUDGET_USD:-25}"
PORT="${PORT:-4173}"
CID="${CID:-main}"
PLATEAU_WINDOW="${PLATEAU_WINDOW:-3}"   # L7 plateau stop: best weighted_total flat for K rounds; 0 disables
SUPERVISE="${SUPERVISE:-0}"             # 1 = invoke the CRDAL supervisor after each round (writes STEER.md)

# --- model-id guard FIRST (M1 model-id locking): fail fast before any filesystem
# scaffolding, so an aborted launch leaves no dead runs/<id>/ skeleton behind.
: "${GENERATOR_MODEL:?set GENERATOR_MODEL (e.g. claude-opus-5) — M1 model-id locking, recorded in RUN_MANIFEST.json}"
if [ "$MODE" = "auto" ]; then
  : "${EVALUATOR_MODEL:?set EVALUATOR_MODEL — invariant 8 + M1: multimodal, family MUST differ from GENERATOR_MODEL}"
fi

# --- claim a unique run dir atomically (same-second relaunch at the same HEAD
# must never share/clobber a run's baton, budget, or events).
BASE_ID="$(date -u +%Y%m%dT%H%M%SZ)-$(git -C "$PROJECT" rev-parse --short HEAD)"
mkdir -p "$PROJECT/runs"
seq=1
while :; do
  RUN_ID="$BASE_ID-$(printf '%03d' "$seq")"
  RUN="$PROJECT/runs/$RUN_ID"
  if mkdir "$RUN" 2>/dev/null; then break; fi
  seq=$((seq + 1))
done
CAND="$RUN/candidates/$CID"
SCHEMA="$SKILL_DIR/schemas/critique.schema.json"
mkdir -p "$CAND"
cp "$SKILL_DIR/templates/NEXT_FINDINGS.json" "$RUN/NEXT_FINDINGS.json"
echo 0 > "$RUN/budgets.json.spent"

# --- RUN_MANIFEST.json (M1 provenance the agent contracts reference): written after
# the model-id checks below prove the ids are real, before round 0 starts.
write_manifest(){
  jq -n --arg run "$RUN_ID" --arg mode "$MODE" --arg gen "$GENERATOR_MODEL" \
    --arg ev "${EVALUATOR_MODEL:-human}" --arg sup "${SUPERVISOR_MODEL:-$GENERATOR_MODEL}" \
    '{run_id:$run, mode:$mode, models:{generator:$gen, evaluator:$ev, supervisor:$sup}}' \
    > "$RUN/RUN_MANIFEST.json"
}

# --- install the skill's subagents into the TARGET project (RUN-2) ---
# `claude --agent <name>` discovers agents in the invocation project's .claude/agents/,
# not in this skill's own tree — so materialize them before the first round.
mkdir -p "$PROJECT/.claude/agents"
cp "$SKILL_DIR/.claude/agents/"*.md "$PROJECT/.claude/agents/"

# --- materialize agent model ids (the shipped files carry REPLACE_WITH_* placeholders;
# the guard at the top proved the env ids are real). Pure-bash literal substitution:
# model ids may contain characters that are special to sed (/, &).
replace_in_file(){ # $1=file $2=literal-from $3=literal-to
  local file="$1" from="$2" to="$3" content
  content="$(cat "$file")"
  printf '%s\n' "${content//"$from"/"$to"}" > "$file"
}
replace_in_file "$PROJECT/.claude/agents/generator.md" REPLACE_WITH_GENERATOR_MODEL_ID "$GENERATOR_MODEL"
replace_in_file "$PROJECT/.claude/agents/supervisor.md" REPLACE_WITH_SUPERVISOR_MODEL_ID "${SUPERVISOR_MODEL:-$GENERATOR_MODEL}"
if [ -n "${EVALUATOR_MODEL:-}" ]; then
  replace_in_file "$PROJECT/.claude/agents/evaluator.md" REPLACE_WITH_MULTIMODAL_MODEL_ID "$EVALUATOR_MODEL"
fi
write_manifest

log(){ printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >> "$RUN/events.log"; }

sum_budget(){ # add a ResultMessage total_cost_usd to the running total (X: no cumulative field)
  local add="$1" cur; cur=$(cat "$RUN/budgets.json.spent"); awk -v a="$cur" -v b="$add" 'BEGIN{print a+b}' > "$RUN/budgets.json.spent"; }

budget_ok(){ awk -v s="$(cat "$RUN/budgets.json.spent")" -v m="$MAX_BUDGET_USD" 'BEGIN{exit !(s<m)}'; }

# Portable critique validator: prefer ajv (full JSON Schema), else fall back to validate-critique.sh (jq).
validate_json(){ # $1=schema $2=doc
  if command -v ajv >/dev/null 2>&1; then ajv validate --spec=draft2020 -s "$1" -d "$2" 2>>"$RUN/events.log"
  else "$SKILL_DIR/scripts/validate-critique.sh" "$2" "$1" 2>>"$RUN/events.log"; fi; }

# UNRENDERABLE seed for this round (capture failure / invalid critique both land here).
unrenderable_seed(){ # $1=round
  jq --arg cid "$CID" --argjson n "$1" '.candidate_id=$cid | .round=$n | .verdict="UNRENDERABLE"' \
    "$SKILL_DIR/templates/NEXT_FINDINGS.json"; }

SERVER_PID=""
cleanup(){ [ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null || true; }
trap cleanup EXIT

stop(){
  echo "$1" > "$RUN/STOP_REASON"; log "STOP $1"
  git -C "$PROJECT" add -A && git -C "$PROJECT" commit -q -m "chore(harness): stop $1 ($RUN_ID)" \
    || log "STOP commit FAILED — round work is UNCOMMITTED"
  # A failed run must be distinguishable from a completed one by exit code.
  if [ "$1" = error ]; then exit 1; fi
  exit 0
}

# Plateau stop (L7): the running-best weighted_total has not improved for
# PLATEAU_WINDOW consecutive rounds. UNRENDERABLE rounds count (weighted "" -> 0):
# a loop stuck on broken builds has plateaued too.
plateaued(){
  [ "$PLATEAU_WINDOW" -gt 0 ] || return 1
  [ -f "$RUN/scores.csv" ] || return 1
  awk -F, -v k="$PLATEAU_WINDOW" '
    { v = $4 + 0; if (NR == 1 || v > best) { best = v; best_at = NR } }
    END { exit !(NR >= k && (NR - best_at) >= k) }' "$RUN/scores.csv"
}

for ((n=0; n<MAX_ROUNDS; n++)); do
  RD="$CAND/round-$n"; mkdir -p "$RD/build" "$RD/shots"
  [ -f "$RUN/AGENT_STOP" ] && stop operator_halt
  budget_ok || stop budget

  # --- STEER injection (read+inject+clear in wrapper) ---
  STEER=""; [ -f "$RUN/STEER.md" ] && { STEER=$(cat "$RUN/STEER.md"); : > "$RUN/STEER.md"; }

  # --- GENERATOR (reads exactly one baton: NEXT_FINDINGS.json) ---
  # Run from $PROJECT so the CLI resolves .claude/agents/ there; a CLI failure is a
  # harness error (stop error), distinct from bad model output (the invalid-critique fallback below).
  log "round $n generate"
  (cd "$PROJECT" && claude --agent generator \
    -p "Read $RUN/NEXT_FINDINGS.json (the baton — the single CURRENT critique, not a transcript),
        DESIGN.md, BRIEF.yaml, tokens/, and $RUN/scores.csv (the running trend, if present). $STEER
        Two-pass plan-then-build into $RD/build. You decide refine|pivot from the scores.csv trend." \
    --output-format json > "$RD/gen.result.json") || { log "round $n generator CLI failed"; stop error; }
  sum_budget "$(jq -r '.total_cost_usd // 0' "$RD/gen.result.json")"

  # --- SERVE the round's build (closes the generate->evaluate loop): keep a stable
  # symlink at runs/<id>/live pointing at the CURRENT round's build. If nothing is
  # already listening on $PORT, the harness serves runs/<id>/live itself, so both
  # seats always evaluate THIS round's output, never a stale page.
  ln -sfn "$RD/build" "$RUN/live"
  if ! curl -sf -m 2 -o /dev/null "http://localhost:$PORT/"; then
    if [ -z "$SERVER_PID" ]; then
      python3 -m http.server "$PORT" --directory "$RUN/live" >/dev/null 2>&1 & SERVER_PID=$!
      log "round $n harness static server pid=$SERVER_PID serving runs/$RUN_ID/live"
      sleep 1
    fi
  fi

  # --- SHARED PINNED CAPTURE (invariant 3 / S4): NOT a seat ---
  # Playwright + axe-core resolve from $PROJECT's node_modules in BOTH modes.
  CAPTURE_OK=1
  if ! "$SKILL_DIR/scripts/capture-shots.sh" "http://localhost:$PORT" "$RD/shots" "$PROJECT"; then
    log "round $n capture failed -> UNRENDERABLE (seat skipped)"
    CAPTURE_OK=0
  fi
  if [ "$CAPTURE_OK" = 1 ]; then
    # Pinned axe-core oracle (machine floor keys; evaluator reads axe-*.json, never runs page JS).
    "$SKILL_DIR/scripts/run-axe.sh" "http://localhost:$PORT" "$RD" "$PROJECT" \
      || log "round $n axe run failed (floor keys fail closed for the evaluator)"
  fi

  # --- EVALUATOR (the ONLY mode branch: pick which seat to invoke) ---
  K=0; OUT="$RD/critique-$K.json"; AUDIT="$RD/critique-$K.audit.json"
  if [ "$CAPTURE_OK" = 0 ]; then
    # R-UNRENDERABLE: no shots exist, so no seat can cite evidence; emit the
    # deterministic UNRENDERABLE verdict instead of aborting the whole run.
    unrenderable_seed "$n" > "$OUT"
  elif [ "$MODE" = "auto" ]; then
    # Materialize the pinned Playwright MCP config (RUN-1): nothing else creates it,
    # and --strict-mcp-config errors out if the file is absent.
    cp "$SKILL_DIR/templates/mcp.json" "$RD/mcp.json"
    (cd "$PROJECT" && claude --agent evaluator \
      --mcp-config "$RD/mcp.json" --strict-mcp-config \
      --allowedTools "mcp__playwright__*" \
      -p "Evaluate http://localhost:$PORT. Use shots/ at $RD/shots and axe results at $RD/axe-*.json (already captured). Emit L6 JSON. NO seat field." \
      --output-format json > "$RD/eval.result.json") || { log "round $n evaluator CLI failed"; stop error; }
    sum_budget "$(jq -r '.total_cost_usd // 0' "$RD/eval.result.json")"
    jq '.structured_output // .result | fromjson? // .' "$RD/eval.result.json" > "$OUT"
  else
    # human seat (RUN-3): render the blank form, then BLOCK until the human saves the
    # filled sheet (or halts via the AGENT_STOP kill-file). A malformed sheet must fall
    # into the invalid-critique -> UNRENDERABLE fallback below, never kill the run.
    cp "$SKILL_DIR/templates/REVIEW-SHEET.md" "$RD/REVIEW-SHEET.md"
    printf 'human seat: fill %s\n            save it as %s to continue (touch %s to halt)\n' \
      "$RD/REVIEW-SHEET.md" "$RD/REVIEW-SHEET.filled.md" "$RUN/AGENT_STOP"
    until [ -f "$RD/REVIEW-SHEET.filled.md" ] || [ -f "$RUN/AGENT_STOP" ]; do sleep 2; done
    [ -f "$RUN/AGENT_STOP" ] && stop operator_halt
    # Wait for the save to finish (editors write non-atomically): size must be
    # nonzero and stable across a poll before the sheet is parsed.
    size=-1
    while :; do
      new_size=$(wc -c < "$RD/REVIEW-SHEET.filled.md")
      if [ "$new_size" -gt 0 ] && [ "$new_size" = "$size" ]; then break; fi
      size=$new_size; sleep 1
    done
    "$SKILL_DIR/scripts/human-seat-to-json.sh" "$RD/REVIEW-SHEET.filled.md" > "$OUT" || true
  fi

  # --- WRAPPER: validate schema + evidence, recompute gate deterministically (R-INJECTION defense) ---
  if [ ! -s "$OUT" ] || ! validate_json "$SCHEMA" "$OUT"; then
    log "round $n invalid critique -> UNRENDERABLE seed"; unrenderable_seed "$n" > "$OUT"
  fi
  # Fail-closed floor (R-HEADLESS-FLOOR): the axe-sourced floor keys are machine
  # facts. If the oracle produced no axe-<w>.json for a viewport, no seat may claim
  # them true — force them false HERE, not just in evaluator prompt text.
  for w in 1440 768 375; do
    if [ ! -f "$RD/axe-$w.json" ]; then
      jq ".quality_floor.responsive_$w=false | .quality_floor.visible_keyboard_focus=false | .quality_floor.contrast_AA_4_5=false" \
        "$OUT" > "$OUT.tmp" && mv "$OUT.tmp" "$OUT"
      log "round $n axe-$w.json missing -> viewport $w floor keys forced false"
    fi
  done
  # Deterministic gate: per_criterion, floor_breaches, blocking count, weighted_total,
  # and verdict are RECOMPUTED from rubric.json — a prompt-injected evaluator cannot
  # award itself a PASS (R-INJECTION; see HARNESS §16-17).
  "$SKILL_DIR/scripts/recompute-gate.sh" "$OUT" "$SKILL_DIR/rubric.json" > "$OUT.tmp" \
    && mv "$OUT.tmp" "$OUT" || { log "round $n recompute-gate failed"; stop error; }
  "$SKILL_DIR/scripts/assert-evidence.sh" "$OUT" "$RD" "$PROJECT" || stop error   # evidence files must exist on disk
  # sidecar provenance (loop-blind): wrapper records seat + any auto-only stats here, never in $OUT
  jq -n --arg seat "$MODE" '{evaluator:{type:$seat}}' > "$AUDIT"

  # --- BATON: merge round critiques -> merged.json -> NEXT_FINDINGS.json ---
  cp "$OUT" "$RD/merged.json"            # single-critique round; hybrid rounds run merge() here
  cp "$RD/merged.json" "$RUN/NEXT_FINDINGS.json"
  "$SKILL_DIR/scripts/render-baton-md.sh" "$RUN/NEXT_FINDINGS.json" > "$RUN/NEXT_FINDINGS.md" || true

  VERDICT=$(jq -r '.verdict' "$RUN/NEXT_FINDINGS.json")
  jq -r '[.candidate_id,.round,.verdict,(.weighted_total//"")]|@csv' "$RUN/NEXT_FINDINGS.json" >> "$RUN/scores.csv"
  log "round $n verdict=$VERDICT (no stop-on-PASS; C8)"

  # --- SUPERVISOR (CRDAL, optional): may write STEER.md for the NEXT round ---
  if [ "$SUPERVISE" = 1 ]; then
    (cd "$PROJECT" && claude --agent supervisor \
      -p "Run dir: $RUN. Review scores.csv and $CAND/round-*/critique-*.json plus shots/ for the
          plateau/fixation/low-novelty triggers in your contract. If (and ONLY if) one fires,
          write a single short nudge to $RUN/STEER.md; otherwise write nothing." \
      --output-format json > "$RD/sup.result.json") \
      || log "round $n supervisor CLI failed (advisory; continuing)"
    sum_budget "$(jq -r '.total_cost_usd // 0' "$RD/sup.result.json" 2>/dev/null || echo 0)"
  fi

  # --- per-round commit (authoritative; Stop hook is only a crash backstop) ---
  git -C "$PROJECT" add -A && git -C "$PROJECT" commit -q -m "chore(harness): round $n $VERDICT ($RUN_ID)" || log "round $n commit FAILED — round work is UNCOMMITTED"
  # NOTE: PASS is recorded, NOT terminal. Loop continues to MAX_ROUNDS / budget / plateau (L7).
  plateaued && stop plateau
done
stop iter_cap
