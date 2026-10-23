---
needs: []
touches: []
effects: []
ships-to: production
---
# <Outcome sentence: what is true once this concern is done>

## Done when

- **C1** <A falsifiable claim someone else can check.> Prove: <how>, on <environment>.

<!-- Everything above this comment is the concern's contract. loop-plan writes it, and loop-design completes
     it with the owner. Drop these comments when you write a real concern.

     needs     what this concern's build relies on: a concern in this loop (`queue`), a concern in another
               loop (`billing/invoices`), or a published decision (`report-pipeline/D1`, `billing/D3`).
               A needed concern is met once its work is on main and each of its claims holds on some
               environment, a lower or local one included; a needed decision must not be superseded.
               What only this concern's proofs rely on is not a need: those proofs wait until their
               environment serves it.
     touches   paths or globs this concern may change; `<repo>:<path>` for another repository.
     effects   the gates from LOOP.md §2 this concern crosses, in plain words ("migration on shared data");
               [] if none. The owner sees them before work starts, and the ship brief lists them.
     ships-to  the environment where every claim must hold: main, staging, production, …
               `main` means the claims are proven on the main branch itself (tests, CI).
     prs       optional: pull requests that belong here but carry no `Concern:` trailer, as numbers or
               `<owner>/<repo>#<n>`. Migrated and hand-made work uses this.
     parked    optional: the D# in this file that parks the concern.

     There is no status field, and there never will be. /loop-status derives the state from git, pull
     requests, what each environment serves, and the Evidence lines below. -->

## Design

### Where we are

<For this concern's touches only. Verified (with evidence), assumed (and how to check it), missing.>

### Options

<Only when there is a real choice: each option's cost, what it breaks, how reversible it is, a recommendation.>

### Approach

<What will be built, citing the decisions it rests on. This is what a build agent reads first.>

## Decisions

<!-- This concern's own decisions. They are private: no other concern may need them. A decision that other
     concerns must rely on belongs in the loop README's Shared decisions. Never renumber; supersede. -->

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

<!-- One row per question: the question in one sentence, the claims it blocks, and what happens if nobody answers.
     Under the table, each open question gets a **Q<n> options** list of 2 to 4 options, each a bold text, a colon
     and its main consequence, with (recommended) at the end of the one you recommend. The default is what
     happens if nobody answers, so it may differ from the recommendation. An answered question is struck through
     with → D# and keeps its list. loop-status's scripts/questions.py reads this format. For example:

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| Q1 | Where does the export run? | C2 | In the web process, behind a 30-second timeout |
| ~~Q2~~ | ~~CSV or JSON?~~ → D1 | | |

**Q1 options**
- **In the web process**: nothing new to deploy, but a large export times out.
- **In a queue worker**: no timeout, and retries come free, but it waits for the `queue` concern. (recommended)

**Q2 options**
- **CSV**: opens in any spreadsheet, but nested fields are flattened. (recommended)
- **JSON**: keeps nested fields, but most readers need a converter.
-->

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

<!-- Append-only. A newer line supersedes an older one; nothing is edited. Every line cites a commit that is
     already on main, because proof from before the merge lives in the pull request:
     - YYYY-MM-DD · C1 · HOLDS · rung 1 · staging @9f3c2e1 · <one line of evidence, with numbers>
     - YYYY-MM-DD · ship · verified · staging @9f3c2e1 · <what was checked after the deploy>
     A spike's answer is the one exception, and may cite the branch it ran on:
     - YYYY-MM-DD · Q2 · HOLDS · rung 4 · local @<branch-sha> · <the answer, and what it rests on> -->

## Shipped

<!-- Written once, by loop-status, when the concern is done: what shipped, where it departs from the design
     above, and what was learned. -->
