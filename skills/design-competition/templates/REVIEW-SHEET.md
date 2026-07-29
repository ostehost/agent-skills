# REVIEW-SHEET (human seat)

You are the evaluator this round. Judge the build like the auto seat would:

1. Look at the pinned screenshots in this round's `shots/{1440,768,375}.png` AND the code in
   `build/` (invariant 8: never score aesthetics from one modality alone).
2. Score each criterion IN ISOLATION on 1-5 (0.5 grid), rationale BEFORE the number
   (see `rubric.md`).
3. Fill the JSON below, then save this file as `REVIEW-SHEET.filled.md` in the same
   directory. The harness is blocked waiting for it.

Notes:
- Keep exactly one fenced ```json block; `human-seat-to-json.sh` extracts the first one.
- Do NOT add seat-identifying keys (`seat`, `confidence`, `samples`, ...) — the wrapper
  strips the known ones (`schemas/forbidden-keys.txt`) and the schema rejects the rest.
- `evidence` values must be files that exist in the round dir (e.g. `shots/1440.png`)
  or runtime oracles (`axe:<rule>`); `assert-evidence.sh` enforces this.
- If the page did not render at a viewport, set `verdict` to `UNRENDERABLE` with a single
  `render_error` change_request, scores null.

```json
{
  "schema_version": "l6/3.0",
  "candidate_id": "main",
  "round": 0,
  "critique_index": 0,
  "viewports": [1440, 768, 375],
  "rubric_ref": "l5/rubric@PLACEHOLDER",
  "axe_core_version": "4.12.1",
  "scores": {
    "design_quality": { "rationale": "", "score": null },
    "originality": { "rationale": "", "score": null },
    "craft": { "rationale": "", "score": null },
    "functionality": { "rationale": "", "score": null }
  },
  "ai_slop_flags": [],
  "quality_floor": {
    "responsive_1440": false, "responsive_768": false, "responsive_375": false,
    "visible_keyboard_focus": false, "contrast_AA_4_5": false
  },
  "change_requests": [],
  "gate": { "per_criterion": {"design_quality": false, "originality": false, "craft": false, "functionality": false}, "floor_breaches": [], "blocking_change_requests": 0 },
  "verdict": "NEEDS_WORK",
  "weighted_total": null,
  "recommendation": "refine",
  "recommendation_rationale": ""
}
```
