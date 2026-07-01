#!/usr/bin/env bash
# Evidence discipline: every change_request whose `evidence` points at a screenshot
# (shots/<w>.png) or a token file (tokens/...:NN) MUST reference a file that exists on disk
# in this round dir. axe:<rule> and console-line evidence are accepted as-is (runtime oracle).
set -euo pipefail
DOC="${1:?critique json}"; RD="${2:?round dir}"
miss=0
while IFS= read -r ev; do
  [ -z "$ev" ] && continue
  case "$ev" in
    shots/*.png)  f="${ev%% *}"; [ -f "$RD/$f" ] || { echo "missing evidence file: $RD/$f" >&2; miss=1; } ;;
    tokens/*)     p="${ev%%:*}"; [ -f "$p" ] || { echo "missing token evidence: $p" >&2; miss=1; } ;;
    axe:*|console:*|network:*) : ;;   # runtime-oracle evidence, no file required
    *) : ;;
  esac
done < <(jq -r '.change_requests[]?.evidence // empty' "$DOC")
[ "$miss" -eq 0 ] || exit 1
echo "ok: evidence resolves for $DOC"
