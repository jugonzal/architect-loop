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
| A planning boundary: the propose step never implements | `loop-plan` and `loop-design` plan only; building starts on request |
| Project-level context every workflow reads first (`openspec/config.yaml`) | `LOOP.md` |
| One folder per change, with small files inside | One folder per loop in `docs/loops/`, one file per concern |
| An explicit verify step before archiving | `loop-prove`, with an evidence ladder and a verdict |
| "Open questions that would change the plan must be asked, not assumed" | `Q#`s, asked one at a time by `loop-design` |

## Different

| OpenSpec | Architect Loop | Why |
| --- | --- | --- |
| The unit is a **change folder**, archived when done; specs are the durable truth | The unit is a **loop** of independent **concerns**, each with a contract (done when, needs, touches, effects, ships-to). Finished loops stay where they are, and git history is the archive | Concerns are built in parallel by separate agents; a contract that names its paths and dependencies is what keeps them from colliding |
| Centre of gravity: **requirements** (`SHALL`, scenarios) | Centre of gravity: **decisions and evidence** (`D#`, `Q#`, `C#`, verdicts bound to commits) | For one architect, the scarce resource is decision attention and trustworthy state, not requirement precision |
| Task checkboxes record progress | **No progress is recorded**: `loop-status` derives each concern's state from git, PRs, environments and evidence | A checkbox someone forgot to tick is a wrong answer to "is it done?"; a derived state cannot be forgotten |
| Verify checks the implementation **against the spec** | Prove checks each concern **against reality**, and can send that concern back to design | Most costly errors were premises that were false, not code that missed a spec |
| Human reviews plans | Human also **holds gates**: merging code, shipping, money, identity, legal, secrets; each concern declares the gates it crosses | Irreversibility lives at shipping; the owner's picture of the system stays current |
| No first-class correction step | **Corrections are first-class commits**; `loop-status` flags drift every run, and `audit` checks every document | Documents go stale; agents trust whatever is written |
| Knowledge lives in specs | Knowledge also lives in **runbooks as actually run** and **dated memory** | Operational traps are the most expensive knowledge to relearn |
| CLI validates structure | No CLI; the skills are plain Markdown, plus two small guard scripts (`check_loop_pr.sh`, `migrate_gen1.py`) | Zero install friction; any agent that reads skills can use it |

## Using both

They compose. A team that wants requirement-level specs can keep OpenSpec's `specs/` as the
behaviour contract and use these skills for the decision, evidence, promotion and record around it.
Nothing here depends on OpenSpec, so the wiring is by convention: name the affected capabilities in a
loop's Intent, copy spec scenarios into concerns' **done when** so `loop-prove` treats them as claims, put the
spec files in each concern's `touches`, and run `loop-status` after OpenSpec's archive.
