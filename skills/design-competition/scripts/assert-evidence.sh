#!/usr/bin/env bash
# Evidence discipline: every change_request whose `evidence` points at a screenshot
# (shots/<w>.png, round-dir relative) or a token file (tokens/...:NN, project-relative)
# MUST reference a file that exists on disk. axe:<rule> and console-line evidence are
# accepted as-is (runtime oracle). PROJECT defaults to five levels above the round dir
# (runs/<id>/candidates/<cid>/round-<n>), matching the harness layout.
set -euo pipefail
DOC="${1:?critique json}"; RD="${2:?round dir}"; PROJECT="${3:-$RD/../../../../..}"
miss=0
while IFS= read -r ev; do
  [ -z "$ev" ] && continue
  case "$ev" in
    shots/*.png)  f="${ev%% *}"; [ -f "$RD/$f" ] || { echo "missing evidence file: $RD/$f" >&2; miss=1; } ;;
    tokens/*)     p="${ev%%:*}"; [ -f "$PROJECT/$p" ] || { echo "missing token evidence: $PROJECT/$p" >&2; miss=1; } ;;
    axe:*|console:*|network:*) : ;;   # runtime-oracle evidence, no file required
    *) : ;;
  esac
done < <(jq -r '.change_requests[]?.evidence // empty' "$DOC")
[ "$miss" -eq 0 ] || exit 1
echo "ok: evidence resolves for $DOC"
