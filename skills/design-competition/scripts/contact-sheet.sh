#!/usr/bin/env bash
# Build a contact sheet across all fan-out candidates for comparative screening (L3).
# Requires ImageMagick `montage`. Marks the current best-so-far candidate id.
set -euo pipefail
RUN="${1:?run dir}"; BEST="${2:-}"   # BEST = candidate id to mark, optional
command -v montage >/dev/null 2>&1 || { echo "contact-sheet: ImageMagick 'montage' not found (brew install imagemagick)" >&2; exit 2; }
SHEET="$RUN/contact-sheet.png"; TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

rows=()
for cdir in "$RUN"/candidates/*/; do
  cid=$(basename "$cdir")
  # newest round's shots for this candidate
  rd=$(ls -d "$cdir"round-*/ 2>/dev/null | sort -V | tail -1 || true)
  [ -z "$rd" ] && continue
  label="$cid"; [ "$cid" = "$BEST" ] && label="$cid  <= BEST-SO-FAR"
  row="$TMP/$cid.png"
  montage -label "$label" \
    "$rd/shots/1440.png" "$rd/shots/768.png" "$rd/shots/375.png" \
    -tile 3x1 -geometry 320x+6+6 -background white "$row"
  rows+=("$row")
done

[ ${#rows[@]} -eq 0 ] && { echo "no candidate shots found" >&2; exit 1; }
montage "${rows[@]}" -tile 1x -geometry +0+10 -background white "$SHEET"
echo "$SHEET"
