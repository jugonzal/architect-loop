---
name: loop-plan
description: Add a new loop to the backlog without losing focus on the current one. Captures the intent, the goals and a first cut of independent concerns as docs/loops/<loop>/, compares the new loop with every loop already tracked and with old proposals, and records each relation at the loosest coupling that works, editing no other loop. Planning only; never implements, and asks only what it needs to capture the idea. Use when the owner has a new initiative, a new direction for the system, an idea to park for later, "add this to the backlog", "we should eventually…", a big item to plan, an RFC to start, or runs /loop-plan.
license: MIT
metadata:
  author: architect-loop
  version: "0.2"
---

# loop-plan

Write a new loop down while the idea is fresh, so the owner can get back to the current one.

A loop is the unit the owner thinks in: a goal the system should move toward. Several can be tracked at
once, and most of them wait in the backlog. This skill gives a new one a home, a first cut of concerns, and
an honest account of how it touches the loops already in flight. Grilling out the details is
`/loop-design`'s job, later, when the owner chooses to start it.

## Boundary

**This skill plans; it does not build.** It writes `docs/loops/<loop>/README.md` and one minimal file per
concern, and nothing else. It never edits another loop's files, never edits code, and never starts
`/loop-design` or `/loop-build` in the same turn.

It commits on a `docs/<loop>-plan` branch and opens a PR that changes only `docs/loops/<loop>/`. That PR
records no evidence, so under `LOOP.md` §2.1 it may merge it itself once
`scripts/check_loop_pr.sh` from the loop-status skill passes. Without that row, the owner merges.

**Without `LOOP.md`:** use `docs/loops/`, the default gates from `loop-init`, `ships-to: production`, leave the
PR for the owner, and mention `/loop-init` once.

## Steps

1. **Read the landscape.** `LOOP.md`; every loop in `docs/loops/` (its README and its concerns' front matter
   and Done when); the titles and summaries in `docs/proposals/`, where earlier attempts and abandoned loops
   live; and `/loop-status`'s one-line view of which loops are active. Keep it to a skim; this is not design.

2. **Capture the intent.** From the owner's words: what changes in the world, for whom, and why now. If one of
   those is missing, ask for it, together with any other gaps, in one batch of at most three questions.
   Do not ask about the how.

3. **Check it is new.** If an active or backlog loop already covers the intent, say so and offer to revise that
   loop through `/loop-design` instead. If an abandoned loop in `docs/proposals/` tried it, say what stopped it
   and carry that into the new loop's Where we are.

4. **Write the goals** as `G1, G2, …`: measurable conditions that mean the whole loop is done, each with how and
   where it is proven. Name the non-goals.

5. **Cut a first set of concerns.** Each concern is one outcome that can be built, proven and shipped on its
   own, with at most three claims (`C#`). Name each by its outcome, not by an order. Default to independent; add
   a `needs` only for a real dependency you can state, never for "it seems to come first". When two concerns would
   share an interface, make the interface its own small concern that both need. Put the riskiest unknown first as
   a question to answer, not as a step. Three to seven concerns is typical; fewer is fine.

6. **Compare with every other loop**, and record what you find in this loop's **Relations**, at the loosest
   coupling that works:
   - **relates**: both loops touch the same area, with no ordering. Say how this loop stays out of the other's way.
   - **needs a decision**: a concern here relies on a decision another loop published (`<loop>/D<n>`). Put it in
     that concern's `needs`, so it goes stale if the decision is superseded.
   - **needs a concern**: a concern here waits for another loop's concern to be done (`<loop>/<concern>`).

   Check for: overlapping `touches` with any active concern, which is a merge conflict waiting to happen; goals
   in tension; decisions this loop would contradict, which become a `Q#` here and never an edit there; and
   concerns that duplicate one elsewhere. Prefer the loosest coupling: an observation over a dependency, a
   dependency on a published decision over one on a concern. If two loops seem to need each other's internals,
   say so: that is a sign the boundary between them is in the wrong place.

7. **Write the files.**
   - `docs/loops/<kebab-slug>/README.md` from [templates/loop.md](templates/loop.md): Intent, Non-goals, Goals,
     Relations, a short Where we are, and any `Q#`s the owner did not answer. Leave Shared decisions empty unless
     the owner decided something in this conversation.
   - One `docs/loops/<loop>/<concern>.md` per concern from [templates/concern.md](templates/concern.md), filled
     only as far as the contract: front matter (`needs`, `touches` as best known, `effects` you can already see,
     `ships-to`) and Done when. Leave Design empty for `/loop-design`.
   - Every question you leave open, in the README or a concern, carries its options in the file that raises it.
     Its row in the Questions table gives the question, what it blocks and the default if unanswered. Under the
     table, a `**Q<n> options**` list gives 2 to 4 options, each written `- **<option>**: <its main consequence>`,
     with `(recommended)` at the end of the one you recommend. The default is what happens if nobody answers, so
     keep it apart from the recommendation. The templates' Questions comment shows an example.

   Drop the templates' guidance comments. Never add a status line: a new loop is in the backlog because nothing
   has started, and `/loop-status` will say so. Read the questions back with
   `python3 scripts/questions.py docs/loops/<loop>` from the loop-status skill: it prints each one as it reads it,
   and exits 1 naming every line it cannot read.

8. **Stop and hand over.** Report in a few lines: the loop, its concerns, its relations (and any that worried
   you), the open questions, and that it is in the backlog. The next command, when the owner wants to start it,
   is `/loop-design <loop>`.

## Quality bar

- Every claim and goal can be checked by someone other than the author, somewhere named.
- Every relation says what is shared and how the coupling stays loose. No relation edits another loop.
- No concern's title contains "and". No concern has more than three claims.
- Gates are visible in `effects` from the first draft, so the owner sees them before anyone builds.
