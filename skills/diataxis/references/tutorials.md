<!-- diataxis: reference -->

# Tutorial rules

Quadrant: tutorial. Compass: action + acquisition. Reader: at study.

A tutorial is a lesson. The learner acquires skill by doing, guided by a tutor
who has already made every decision for them. Success is a learner who
finishes, sees each promised result, and trusts the product afterward.

## Signals

Canonical tutorial language, quoted as signal strings:

- `In this tutorial, we will …` opens the lesson.
- `First, do x. Now, do y.` sequences the steps.
- `The output should look something like …` sets the expectation.
- `Notice that …` and `Remember that …` direct attention.
- `Let's check …` keeps the voice shared.
- `You have built a …` closes the lesson.

## Do

- Open with what the learner will build and see at the end.
  - Why: a visible destination replaces a list of learning objectives.
- Write every step so it produces a visible, checkable result.
- Use the first-person plural voice so the tutor accompanies the learner.
- Show expected output after each step that changes visible state.
  - Why: output is how the learner confirms the lesson is on track.
- Point out what the learner should notice in each result.
- Keep one path from start to finish for every reader.
- Limit explanation to one sentence with a link to explanation.
- Test the full lesson from a clean environment before publishing.
  - Why: one broken step ends the lesson for every learner.

## Do not

- Offer alternatives or optional paths; pick one and link how-to guides.
  - Why: choices transfer decisions to a learner who cannot make them yet.
- Promise what the learner will learn; show what they will build.
- Add option tables or parameter lists; link the reference page instead.
- Insert background sections such as Understanding or About; link explanation.
- Assume prior knowledge the lesson never built; state prerequisites at the top.

## Neighbour bleed

| Neighbour | Shared axis | Leak | Audit rule |
|---|---|---|---|
| how-to | action | alternatives, optional paths, steps with no tutor voice | `tut-choice`, `tut-reads-as-howto` |
| explanation | acquisition | background sections, why digressions | `tut-explanation-heading`, `tut-why-digression` |
| reference | none (diagonal) | option tables, term definition lists | `tut-reference-dump` |
| none | none | promises of what the learner will learn | `tut-learning-claim` |

Operating-system branches under a `## On Windows` style heading are not choices.
A single sentence of explanation plus a link is not a digression.

## Skeleton

````markdown
---
diataxis: tutorial
---

# Build <a concrete thing>

In this tutorial, we will build <thing>. You need <prerequisite>.

## <First milestone>

First, we <action>:

```console
$ <command>
<expected output>
```

You should see <expected output>. Notice that <the one detail worth noticing>.

## What you have built

You have built <thing>. To adapt it, see [<goal>](../how-to/<goal>.md).
````

## Example

````markdown
Before (bleeds into how-to and explanation):

## Start the server

Alternatively, you could run the server in Docker. Understanding the event loop
helps here, because the server handles every request on one thread.

After:

## Start the server

Now we start the server with `weather serve`. You should see `listening on :8080`.
It answers on one thread ([About the event loop](../explanation/event-loop.md)).
````
