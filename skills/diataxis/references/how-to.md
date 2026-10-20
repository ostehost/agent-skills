<!-- diataxis: reference -->

# How-to rules

Quadrant: how-to. Compass: action + application. Reader: at work.

A how-to guide gives directions to a competent user who already has a goal.
It addresses a real-world problem and stops when the goal is reached. The
reader brings the context; the guide brings the sequence.

## Signals

Canonical how-to language, quoted as signal strings:

- `This guide shows you how to …` states the goal.
- `If you want x, do y.` handles a real fork.
- `To achieve w, do z.` ties an action to its purpose.
- `Refer to the x reference guide for a full list of options.` links out.

## Do

- Title each guide with How to plus the reader's goal.
  - Why: readers scan titles for their goal, not for tool names.
- State the goal and starting assumptions in one short opening paragraph.
- Write actions as imperatives in the order the reader performs them.
- Use conditional imperatives when real situations fork: if X, do Y.
- Assume a competent reader who already knows what they want.
- Link reference pages for full option lists and exact values.
- File troubleshooting pages as how-to guides titled Troubleshooting plus the symptom.
- End when the goal is reached; link related guides afterward.
  - Why: steps past the goal dilute the guide and hide the finish.

## Do not

- Teach concepts or reassure the reader; link explanation pages instead.
  - Why: a reader at work needs the next action, not a lesson.
- Write tool-operation guides disconnected from purpose; frame steps around goals.
- Paste complete parameter tables; link the reference entry instead.
- Title guides with bare nouns or gerunds; use How to or Troubleshooting.
- Pad the guide for completeness; omit steps the goal does not need.

## Neighbour bleed

| Neighbour | Shared axis | Leak | Audit rule |
|---|---|---|---|
| tutorial | action | lesson tone, reassurance, learning promises | `howto-teaching-tone` |
| reference | application | full option or parameter tables | `howto-option-table` |
| explanation | none (diagonal) | concept sections, paragraphs with no action | `howto-concept-heading`, `howto-explanation-block` |
| none | none | titles that do not name the goal | `howto-title` |

A short statement of fact right after a step reports its result; it is not a
lecture. The opening paragraph states only the goal and starting assumptions.

## Skeleton

````markdown
---
diataxis: how-to
---

# How to <achieve the goal>

This guide shows you how to <goal>. It assumes <starting state>.

1. <Action> `<command or path>`.
2. <Action>.

   If <situation>, <alternative action>:

   ```console
   $ <command>
   ```

3. <Action that completes the goal>.

## Related reference

- [<Entry>](../reference/<entry>.md)
````

## Example

````markdown
Before (bleeds into tutorial and explanation):

# Configuring backups

Don't worry if backups are new to you. Backups protect data because disks fail.

After:

# How to schedule nightly backups

This guide shows you how to schedule a nightly backup. It assumes the CLI is installed.

1. Run `backup schedule --at 02:00`.
2. Check the schedule with `backup list`.

For every flag, see [backup schedule](../reference/backup-schedule.md).
````
