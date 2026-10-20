# Widget owners can export their widgets

**Intent.** Owners export their widgets to keep a copy of their own. A fixture loop for questions.py.

## Goals

- **G1** An owner exports 10,000 widgets in under a minute. Prove: a timed export, on staging.

## Shared decisions

| # | Decision | Decided by, date | Notes |
| --- | --- | --- | --- |
| D1 | Exports are CSV. | Owner, 2026-10-01 | Closes Q2 |
| D2 | Deleted widgets are left out. | Owner, 2026-10-01 | Closes Q3 |

## Questions

<!-- A guidance comment that the writer kept. Nothing inside a comment is read:

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| Q7 | Is a question inside a comment read? | C1 | No |

**Q7 options**
- **Yes**: the comment would count. (recommended)
- **No**: the comment is guidance only.
-->

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| Q1 | Where do exports run? | `export-format`, `export-worker` (C2) | In the web process, behind a 30-second timeout |
| ~~Q2~~ | ~~CSV or JSON?~~ → D1 | | |
| ~~Q3~~ | ~~Include deleted widgets?~~ → D2 | | |

**Q1 options**
- **In the web process**: nothing new to deploy, but an export of more than about 10,000 widgets times out.
- **In a queue worker**: no timeout and retries for free, but it waits for `export-worker`. (recommended)
- **On the owner's device**: no server cost, but every client needs its own exporter.

**Q2 options**
- **CSV**: opens in any spreadsheet; nested fields are flattened. (recommended)
- **JSON**: keeps nested fields, but most owners need a converter to read it.

## Evidence

## Shipped
