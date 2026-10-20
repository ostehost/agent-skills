<!-- diataxis: reference -->

# Reference rules

Quadrant: reference. Compass: cognition + application. Reader: at work.

Reference describes the machinery: commands, options, fields, endpoints, and
limits. Readers consult it in the middle of a task, so every entry is
accurate, complete for its scope, and found by lookup. Its structure follows
the product's structure.

## Signals

Canonical reference language, quoted as signal strings:

- `X inherits Y's defaults; it is available as Z.` states facts about the machinery.
- `Sub-commands are: a, b, c.` lists members.
- `You must use a. You must not apply b unless c. Never d.` states constraints.

## Do

- Describe the machinery neutrally, in the order the product structures it.
  - Why: readers navigate reference by the product's own shape.
- Use one consistent entry pattern for every command, option, or field.
- Lead each entry with name, type, default, and allowed values.
- State constraints as plain rules, such as must, must not, never.
- Include a short usage example beside entries that need one.
- Link how-to, tutorial, or explanation pages instead of inlining them.
- Mirror product structure in headings so readers find entries by lookup.

## Do not

- Add opinions, recommendations, or superlatives; state facts and measured limits.
  - Why: a reader mid-task needs facts that hold in every context.
- Narrate history or design rationale; move it to an explanation page.
- Write numbered task procedures inside entries; link the how-to guide.
- Use first-person voice or hedges; write declarative statements of fact.
- Wrap entries in long prose paragraphs; use tables, lists, and definitions.

## Neighbour bleed

| Neighbour | Shared axis | Leak | Audit rule |
|---|---|---|---|
| explanation | cognition | rationale, history, opinion, first-person voice | `ref-why-digression`, `ref-opinion`, `ref-narrative-voice` |
| how-to | application | numbered task procedures | `ref-procedure` |
| tutorial | none (diagonal) | story voice, long narrative paragraphs | `ref-narrative-voice`, `ref-narrative-paragraph` |
| none | none | hedges and promotional wording | `ref-hedge`, `ref-marketing` |

Constraint wording such as `You must`, `must not`, and `Never` is reference
language. A fenced usage example is not a procedure.

## Skeleton

````markdown
---
diataxis: reference
---

# `<command>`

<One sentence: what the command does.>

## Synopsis

```text
<command> [--option VALUE] ARGUMENT
```

## Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--option` | string | `value` | <What it sets.> |

## See also

- [How to <goal>](../how-to/<goal>.md)
````

## Example

````markdown
Before (bleeds into explanation):

`--retries` sets the retry count. We chose three because, historically, the
upstream API dropped about one request in fifty, and that might change.

After:

| Option | Type | Default | Description |
|---|---|---|---|
| `--retries` | integer | `3` | Retry attempts per request. Must be 0-10. |

Background: [About retries](../explanation/retries.md).
````
