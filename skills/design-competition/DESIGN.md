---
# L0 FROZEN brief front matter. Pin the design.md spec commit you validated against.
design_md_spec_commit: "REPLACE_WITH_PINNED_SHA"   # design.md is ALPHA — pin it
brief_hash: ""                                      # filled by just verify-substrate
frozen: true
viewports: [1440, 768, 375]                        # invariant 3 (widths). heights in capture-shots.sh
---

# DESIGN.md — Frozen Brief

> Canonical 8 sections in order (Google design.md), then two harness extensions.
> Edit ONLY at run setup; freeze before round 1. Generator may not alter this file.

## 1. Overview
One concrete product, one audience, one job (a single user action). Tone + tone_extreme.
State the ONE place boldness is spent (SKILL.md: "spend boldness in one place").

## 2. Colors
Semantic roles only (--color-bg / -fg / -accent / -muted / -danger ...). 4-6 seed hexes
map into tokens/primitives.tokens.json ramps. No raw hex in components.

## 3. Typography
Display / body / utility families. Type-size ramp is frozen (see primitives ramp).

## 4. Layout
Prose + ASCII wireframe. Per-viewport intent for 1440 / 768 / 375.

## 5. Elevation & Depth
Shadow/elevation scale (frozen). Note: "shadows at 0.1 opacity" is practitioner lore (verified:false).

## 6. Shapes
Radius scale, border treatment (frozen ramp).

## 7. Components
Component inventory the build must produce. Each binds tokens via var(--*).

## 8. Do's and Don'ts
VERIFIED SKILL.md tells to avoid: cluster_cream_serif, cluster_dark_acid, cluster_broadsheet,
motion_scatter, numbered_markers, copy_templated. Practitioner lore stays advisory.

## 9. Responsive Behavior (harness extension)
Exactly what must hold at 1440 / 768 / 375. These map to floor keys
responsive_1440 / responsive_768 / responsive_375.

## 10. Signature (harness extension)
The ONE memorable, brief-specific signature element. Must render at all three viewports.
Generic/templated signatures are scored down on the originality axis.
