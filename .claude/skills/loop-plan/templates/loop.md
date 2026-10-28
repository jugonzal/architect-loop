---
owner: <the loop owner's GitHub login>
members: []
---
# <Loop title: the change in the world, stated as an outcome>

**Intent.** <Two or three sentences: what changes, for whom, and why now.>
**Non-goals.** <What this loop deliberately leaves out.>

<!-- This README is the loop. Its concerns are the other files in this folder, and it never lists them, so
     adding a concern never edits a shared file. loop-plan writes this file and loop-design (with the owner)
     keeps it current. Nothing here records status: /loop-status derives it. Drop these comments when you
     write a real loop. The front matter names people by GitHub login: `owner:` is the loop's one owner, its
     architect, and `members:` the others who see its items but do not act on them. /loop-status sends each
     item to the holder of the gate it crosses in LOOP.md §2, and any other item to the owner. To park the
     loop, add `parked: D<n>` to the front matter, naming the decision. -->

## Goals

- **G1** <A measurable condition that means the whole loop is done.> Prove: <how>, on <environment>.

## Relations

<!-- Written by loop-plan from a read of every other loop in docs/loops/ and of docs/proposals/, and kept
     current by loop-design. One line per loop that matters, at the loosest coupling that works:
       relates           awareness only: a shared area, no ordering
       needs a decision  a concern here needs `<loop>/D<n>`, a decision that loop published
       needs a concern   a concern here needs `<loop>/<concern>` to be done first
     Never edit another loop's files to record a relation. -->

- **<other-loop>**: relates. <What is shared, and how this loop stays out of its way.>

## Where we are

<Verified from code and environments for this loop's area: verified (with evidence), assumed (and how to
check it), missing. Concerns add the detail for their own touches.>

## Shared decisions

<!-- Decisions that concerns in this loop, or other loops, may rely on by naming them in `needs`. Once a concern
     relies on one it is immutable: supersede it with a new row, never edit it. Never renumber. -->

| # | Decision | Decided by, date | Notes |
| --- | --- | --- | --- |

## Questions

<!-- One row per question: the question in one sentence, the concerns or goals it blocks, and what happens if
     nobody answers. Under the table, each open question gets a **Q<n> options** list of 2 to 4 options, each a
     bold text, a colon and its main consequence, with (recommended) at the end of the one you recommend. The
     default is what happens if nobody answers, so it may differ from the recommendation. An answered question is
     struck through with → D# and keeps its list. A question whose answer crosses a gate in LOOP.md §2 ends its
     Question cell with (gates: <key>), and waits on that gate's holder. loop-status's scripts/questions.py reads
     this format. For example:

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| Q1 | Where do exports run? | `export-worker`, G1 | In the web process, until G1's timing fails |
| ~~Q2~~ | ~~One export format, or one per client?~~ → D1 | | |

**Q1 options**
- **In the web process**: nothing new to deploy, but G1's 10,000 widgets may not fit in its timeout.
- **In a worker**: no timeout, but `export-worker` needs a queue first. (recommended)

**Q2 options**
- **One format**: one exporter to keep, and every client reads it. (recommended)
- **One per client**: each client gets its best fit, at the cost of an exporter each.
-->

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

<!-- Append-only, for the goals. Every line cites a commit already on main:
     - YYYY-MM-DD · G1 · HOLDS · rung 1 · production @<sha> · <one line of evidence> -->

## Shipped

<!-- Written once, by loop-status, when every concern is done and every goal holds: what shipped, where it
     departs from this text, and what was learned. -->
