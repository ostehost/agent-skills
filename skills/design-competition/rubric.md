# Rubric (human-readable) — four criteria, 1-5 on a 0.5 grid

VERIFIED: exactly four criteria; weight DIRECTION = design+originality OVER craft+functionality.
UNVERIFIED: every number (weights, thresholds, scale). Score each criterion IN ISOLATION,
rationale BEFORE the number. You MUST look at the rendered shots/{1440,768,375}.png (invariant 8).

## design_quality (weight 0.35, threshold 3)  [creative axis]
Does it look genuinely good and intentional across all three viewports?

## originality (weight 0.35, threshold 3)  [creative axis]
Is the signature brief-specific and non-templated? Penalize the SKILL.md slop clusters.

## craft (weight 0.20, threshold 2)  [execution axis]
Alignment, spacing rhythm, token conformance, contrast. Largely machine-checkable.

## functionality (weight 0.10, threshold 2)  [execution axis]
Does the one job work? Keyboard reachable? No console errors?

## Quality floor (gated, PARTIAL — axe ~57% coverage)
responsive_1440 / responsive_768 / responsive_375 / visible_keyboard_focus / contrast_AA_4_5.
Any false => NEEDS_WORK. You MAY add advisory a11y change_requests for the ~43% axe can't test
(logical focus order, meaningful alt text, 2.4.11 focus-not-obscured); these do NOT change floor keys.
Standard targeted: WCAG 2.2 AA (current W3C Recommendation).

## Few-shot anchors  (FILL FROM A REAL GOLD-SET — do NOT fabricate)
<!-- anchor: design_quality=5 -> shots ref: __________  rationale: __________ -->
<!-- anchor: design_quality=3 -> shots ref: __________  rationale: __________ -->
<!-- anchor: design_quality=1 -> shots ref: __________  rationale: __________ -->
<!-- anchor: originality=5    -> shots ref: __________  rationale: __________ -->
<!-- anchor: originality=2    -> shots ref: __________  rationale: __________ -->
<!-- repeat per criterion; same anchors seed BOTH seats (calibration/anchors.jsonl) -->
