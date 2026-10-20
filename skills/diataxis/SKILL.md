---
name: diataxis
description: "Classifies, writes, and audits Diátaxis docs as tutorial, how-to, reference, explanation, or landing. Use when creating, editing, or restructuring docs/ pages or any README.md."
---

<!-- diataxis: how-to -->

# How to write and audit Diátaxis documentation

Use this skill whenever a task creates, edits, moves, splits, or deletes a page
under `docs/` or any `README.md`. Every page serves one reader need. The
receipt fixes that need before writing; the audit checks it afterward.

## Compass

Ask both questions of the whole page, then of each section.

| Content informs | Reader is | Quadrant | Rules |
|---|---|---|---|
| action | acquiring skill (study) | tutorial | [references/tutorials.md](references/tutorials.md) |
| action | applying skill (work) | how-to | [references/how-to.md](references/how-to.md) |
| cognition | applying skill (work) | reference | [references/reference.md](references/reference.md) |
| cognition | acquiring skill (study) | explanation | [references/explanation.md](references/explanation.md) |

- Ask whether the reader consults it mid-task: reference, not explanation.
- Ask whether it reads well away from the product: explanation.
- Ask whether the reader studies or works: tutorial or how-to.
- Ignore basic versus advanced; it does not separate tutorial from how-to.
- Expect bleed between neighbours; tutorial and how-to collapse is worst.

## Workflow

The docs root is `docs/`, or the content directory named by `mkdocs.yml`,
`conf.py`, `docusaurus.config.*`, or `astro.config.*`. Add `--plan` to the
baseline audit for a restructure; it writes nothing.

1. Survey the docs root and run the baseline audit first.

   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/audit_quadrant.py <docs-root>
   ```

2. Run the receipt helper for every asset you will touch.

   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/audit_quadrant.py --receipt --operation <create|edit|move|split|delete> <path>
   ```

3. Print the completed receipt before the first write to each asset.
4. Apply the decision table; leave each `escalate` asset untouched and report it.
5. Read the rules file for each quadrant the receipt names.
6. Write the page following the loaded quadrant rules file.
7. Run the strict audit on touched files until it exits zero.

   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/audit_quadrant.py --strict <touched files>
   ```

8. Report receipts, audit commands, exit codes, and changed paths.

Outside Claude Code, read `${CLAUDE_SKILL_DIR}` as the directory holding this file.
Run `--list-rules` to see every audit rule, its severity, and its destination.

## Quadrant Classification Receipt

```json
{
  "receipt": "diataxis/quadrant-classification",
  "schema_version": 1,
  "asset": "docs/how-to/rotate-api-keys.md",
  "operation": "create",
  "reader_need": "Operator rotates a leaked API key without downtime.",
  "compass": {"informs": "action", "serves": "application"},
  "quadrant": "how-to",
  "declared": {"quadrant": "how-to", "source": "path"},
  "inferred": "insufficient-signal",
  "strongest_alternative": {"quadrant": "tutorial", "rejected_because": "Reader already runs the service; no lesson needed."},
  "confidence": "high",
  "contamination_risks": ["howto-option-table"],
  "decision": "proceed",
  "destination": null,
  "split_plan": [],
  "handoff": null,
  "audit_command": "python3 skills/diataxis/scripts/audit_quadrant.py --strict docs/how-to/rotate-api-keys.md"
}
```

The helper prefills `declared`, `inferred`, `strongest_alternative.quadrant`,
`contamination_risks`, `handoff`, and `audit_command`. Fill the `null` fields.

- Keep `reader_need` and `rejected_because` to one line each.
- Set `compass.informs` to `action|cognition|mixed` and `compass.serves` to `acquisition|application|mixed`.
- Set both compass answers to `mixed` for a landing receipt.
- Set `quadrant` to one of the four quadrants, or `landing`.
- Copy the challenger into `strongest_alternative`; when null, use the action/cognition neighbour.
- Set `confidence` to `high` when both compass answers are single-valued.
- Set `confidence` to `medium` for one mixed answer or a contradicted declaration.
- Set `confidence` to `low` when both answers are mixed, except landing.
- Set `confidence` to `high` on a landing receipt that only routes.
- Treat a `none` declared source as no declaration, never a disagreement.
- Copy audit finding ids into `contamination_risks`, plus any expected leak.
- Set `destination` to the new path when the operation is move.
- Fill `split_plan` with `{content, destination, quadrant}` entries when splitting.
- Print one receipt per asset per task; reprint only if classification changes.

## Decision table

Apply the first matching row. Treat no match as `escalate`.

| Condition | Decision |
|---|---|
| asset is `README.md` or a quadrant index page | `proceed` as `landing`; README sets `handoff: readme-standard` |
| `confidence` is `low` | `escalate`: report and ask; write nothing to the asset |
| either compass answer is `mixed` | `split`: one destination page per quadrant |
| `declared.source` is not `none` and `quadrant` differs from `declared.quadrant` | `proceed` with `operation: move` and `destination`; for `create`, change the target path instead |
| `declared.source` is `none` | `proceed` in place; add `diataxis: <quadrant>` front matter |
| any other case | `proceed` |

Load `references/<quadrant>.md` for the receipt's `quadrant` and for each
`split_plan[].quadrant`. A `landing` receipt loads no quadrant reference.

## Layout

The standard quadrant directories are `docs/tutorials/`, `docs/how-to/`,
`docs/reference/`, and `docs/explanation/`.

- Create `docs/<quadrant>/` only together with its first real page.
- Prefer existing quadrant directory names and the docs tool's layout.
- Default to the four standard quadrant directory names under `docs/`.
- Give each quadrant directory an index page that introduces its pages.
- Declare front matter on index pages that hold content, not routing.
- Keep unordered landing lists to seven items; group or order longer ones.
- Split by audience or platform first when the product demands it.
- Add `diataxis: <quadrant>` front matter only where the path cannot declare it.

## README.md and readme-standard

- Classify every `README.md` as `landing`: orient, then route into quadrants.
- Load `readme-standard`, when installed, for README structure, tone, and gates.
- Place content leaving a README in the matching `docs/` quadrant.
- Keep the README quick start short; move longer lessons into a tutorial.

## Do

- Print a Quadrant Classification Receipt before the first documentation write.
  - Why: classification after writing rationalizes whatever got written.
- Run the receipt helper to prefill declared, inferred, and challenger fields.
  - Why: mechanical evidence keeps the challenger honest.
- Answer both compass questions for the whole asset, then per section.
  - Why: a page can pass wide and fail close up.
- Name the strongest alternative quadrant and the axis that rejects it.
  - Why: the nearest neighbour is the likeliest misclassification.
- Load only the reference files for quadrants named in the receipt.
- Split mixed assets so each page serves exactly one reader need.
- Hand README.md structure to readme-standard; classify the README as landing.
- Create a quadrant directory only together with its first real page.
- Run the strict audit on every touched file until it exits zero.
- Report each receipt, audit command, exit code, and changed path.

## Do not

- Create empty quadrant folders or placeholder pages; add pages with content.
  - Why: empty scaffolding signals structure the docs do not have.
- Edit documentation before printing its receipt; classify the asset first.
- Proceed on low confidence; set decision to escalate and ask.
- Paste reasoning transcripts into the receipt; keep each field one line.
- Duplicate readme-standard rules here; link to that skill instead.
- Suppress audit findings to pass; fix the content or split it.
- Reclassify pages silently; set the receipt operation to move instead.

## Sources

- Diátaxis by Daniele Procida, https://diataxis.fr/ (CC BY-SA 4.0); this skill
  paraphrases it and quotes only short signal phrases.
- Compass: https://diataxis.fr/compass/ · Map: https://diataxis.fr/map/ ·
  Workflow: https://diataxis.fr/how-to-use-diataxis/ · Quality:
  https://diataxis.fr/quality/ (the audit checks structure, not deep quality)
- Landing pages and hierarchies (page removed Aug 2026):
  https://github.com/evildmp/diataxis-documentation-framework/blob/de7a2d8/complex-hierarchies.rst
