<!-- diataxis: reference -->

# Explanation rules

Quadrant: explanation. Compass: cognition + acquisition. Reader: at study.

Explanation deepens understanding away from the keyboard. It answers why
questions, connects the topic to context and history, and admits perspective
and opinion. It reads well in an armchair, with the product closed.

## Signals

Canonical explanation language, quoted as signal strings:

- `The reason for x is because historically, y …` gives context.
- `W is better than z, because …` takes a position.
- `An x in system y is analogous to a w in system z.` draws a connection.
- `Some users prefer w (because z).` weighs alternatives.
- `An x interacts with a y as follows: …` describes a relationship.

## Do

- Title each page as a topic that reads naturally after About.
  - Why: the title bounds the page around one subject.
- Bound each page by one real or imagined why question.
- Connect the topic to design decisions, history, and constraints.
- Compare alternatives and state opinions along with the evidence for them.
- Use short illustrative code only when it clarifies a concept.
- Link how-to guides and reference entries for anything the reader does.

## Do not

- Write numbered command procedures or terminal sessions; move them to how-to.
  - Why: instructions pull the reader out of study and into work.
- Embed option or parameter tables; link the reference entry instead.
- Add Steps, Procedure, or Installation sections; link the matching how-to guide.
- Let the page absorb neighbouring topics; split them into separate explanations.

## Neighbour bleed

| Neighbour | Shared axis | Leak | Audit rule |
|---|---|---|---|
| reference | cognition | option or parameter tables | `exp-option-table` |
| tutorial | acquisition | lesson-style imperative prose | `exp-imperative-prose` |
| how-to | none (diagonal) | numbered procedures, terminal steps, procedure headings | `exp-procedure-list`, `exp-terminal-steps`, `exp-procedure-heading` |

A numbered list of reasons is not a procedure. A shell fence introduced as an
illustration, without an instruction to run it, is not a terminal step.

## Skeleton

````markdown
---
diataxis: explanation
---

# About <topic>

<The why question this page answers, stated plainly.>

## Context

<History, constraints, and the problem the design solves.>

## Alternatives and trade-offs

<Approaches considered, who prefers each, and the reasons.>

## Related

- [How to <goal>](../how-to/<goal>.md)
- [<Entry> reference](../reference/<entry>.md)
````

## Example

````markdown
Before (bleeds into how-to):

## Installation

Caching speeds up reads. Run the following to enable it:

```bash
cache enable --ttl 300
```

After:

# About read caching

Caching trades freshness for speed. A cached read skips the database, so a
value can lag behind the source for up to the TTL. To turn caching on, see
[How to enable caching](../how-to/enable-caching.md).
````
