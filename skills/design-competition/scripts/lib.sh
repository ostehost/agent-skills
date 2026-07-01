# Shared skill-root resolution for design-competition/scripts/*.sh. Source, don't
# execute: sets SKILL_DIR to the skill root (parent of scripts/). Uses
# ${BASH_SOURCE[0]} rather than $0 so it resolves correctly even if a caller is
# ever sourced instead of exec'd.
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
