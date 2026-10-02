# Relation to OpenSpec

[OpenSpec](https://openspec.dev/) ([repo](https://github.com/Fission-AI/OpenSpec)) is a spec-driven
framework for AI coding assistants: `explore → propose → apply → verify → archive`, with each change
as a folder of `proposal.md`, delta `specs/`, `design.md` and `tasks.md`, driven by a CLI and
distributed as skills and slash commands. This repository borrows its shape and differs in its centre
of gravity.

## Borrowed

| From OpenSpec | Here |
| --- | --- |
| One skill per workflow stage, installable via skills.sh or as slash commands | `loop-*` skills, Claude Code plugin, skills.sh |
| Artifact templates with per-section instructions | `templates/` inside the skills that write them |
| A planning boundary: the propose step never implements | `loop-frame` plans only; building starts on request |
| Project-level context every workflow reads first (`openspec/config.yaml`) | `LOOP.md` |
| An explicit verify step before archiving | `loop-prove`, with an evidence ladder and a verdict |
| "Open questions that would change the plan must be asked, not assumed" | `Q#` vs "defaults this plan assumes (veto any)" |

## Different

| OpenSpec | Architect Loop | Why |
| --- | --- | --- |
| The unit is a **change folder**, archived when done; specs are the durable truth | The unit is a **living proposal**, updated in place; git history is the archive | Decisions, gates and departures accumulate across many PRs; one document that is always current is what a new session needs |
| Centre of gravity: **requirements** (`SHALL`, scenarios) | Centre of gravity: **decisions and evidence** (`D#`, `Q#`, `G#`, verdicts) | For one architect, the scarce resource is decision attention and trustworthy state, not requirement precision |
| Verify checks the implementation **against the spec** | Prove checks the plan **against reality**, and can send it back to Frame | Most costly errors were premises that were false, not code that missed a spec |
| Human reviews plans | Human also **holds gates**: merge, promote, money, identity, legal, secrets | Irreversibility lives at promotion; the owner's picture of the system stays current |
| No first-class correction step | **Corrections are first-class commits**; `loop-reconcile` audits drift | Documents go stale; agents trust whatever is written |
| Knowledge lives in specs | Knowledge also lives in **runbooks as actually run** and **dated memory** | Operational traps are the most expensive knowledge to relearn |
| CLI validates structure | No CLI; the skills are plain Markdown | Zero install friction; any agent that reads skills can use it |

## Using both

They compose. A team that wants requirement-level specs can keep OpenSpec's `specs/` as the
behaviour contract and use these skills for the decision, evidence, promotion and record around it.
Nothing here depends on OpenSpec, so the wiring is by convention: list the affected capabilities on
the proposal's `Area:` line, copy spec scenarios into plan steps' **done when** so `loop-prove`
treats them as claims, and run `loop-record` after OpenSpec's archive.
