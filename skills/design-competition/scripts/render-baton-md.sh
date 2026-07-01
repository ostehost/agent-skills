#!/usr/bin/env bash
# Render the loop-read baton (NEXT_FINDINGS.json) into the human mirror NEXT_FINDINGS.md.
# The loop NEVER reads the .md; this is human-only. Deterministic; no provenance leaked.
set -euo pipefail
J="${1:?NEXT_FINDINGS.json}"
printf '<!-- DERIVED MIRROR of NEXT_FINDINGS.json. The loop NEVER reads this file. -->\n'
printf '# NEXT_FINDINGS (human mirror)\n\n'
printf '**verdict:** %s\n\n' "$(jq -r '.verdict' "$J")"
printf '## change requests (evidence-bound)\n'
jq -r '.change_requests[]? | "- [\(.severity)] \(.criterion): \(.observed) (\(.evidence)) -> \(.fix // "")"' "$J"
printf '\n**recommendation (advisory):** %s\n' "$(jq -r '.recommendation' "$J")"
