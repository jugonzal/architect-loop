# Failure modes and guardrails

Each guardrail in the method exists because something went wrong first.

| Failure | What it cost | Guardrail | Where it lives |
| --- | --- | --- | --- |
| Status lines claimed work that was not deployed, or missed work that was | A reader trusted a diagnostic that was actually silent; a gate was recorded unmet in three places while met | Status is no longer written: `loop-status` derives it from what the environment serves, every time | `loop-status` |
| A plausible root cause was credited for a fix it did not make | Rounds of guessing on a frozen video player | Competing hypotheses and an A/B on identical code before crediting a cause; retract in writing | `loop-diagnose` |
| Runbook steps were written before they were run | Certificate issuance failed five different ways on first real use | Runbooks are marked draft until run, then rewritten "as actually run" with dated traps | `loop-runbook` |
| Scripts passed locally and failed in the container | Silent failures in ingest hooks whose stderr nobody saw | Prove on the environment that matters, and record environment differences as traps | `loop-prove` traps, `LOOP.md` §7 |
| A stale monitor on a laptop paged as "production" | A day of false alerts | Environment identity is a parameter checked at the source; incidents examine where each signal came from | `loop-incident` step 3 |
| A config regeneration run without one flag dropped TLS on staging | An HTTPS outage | Verify what the environment serves after every change, TLS included; record the flag as a runbook trap | `loop-ship` step 5, `loop-runbook` |
| Calibration rested on a single real sample | A ranker tuned to one game | Report sample sizes; one run is a case, not a calibration | `loop-prove` traps |
| The full test suite was flaky under parallel runs | False red builds | Record known quirks next to the command that avoids them; report failures as environmental only with evidence | `LOOP.md` §4 and §7, `loop-build` step 7 |
| Agents built on the premise the docs gave them | Work built toward a state the system was not in | "Where we are" is written from code and environment, sorted into verified / assumed / missing | `loop-design` step 2 |
| Agents claimed steps and recorded built, merged and deployed by hand | Docs commits, and sometimes whole branches, spent on facts git already knew; records that lagged behind reality | Nothing records status; the open PR is the claim; `loop-status` derives the rest | `loop-status`, `loop-build` step 4 |
| Every parallel branch began by editing the same living proposal, to claim its step | Contention for one file, and room for collisions (two branches each adding a `D5`) | One file per concern, namespaced IDs, and code PRs that never touch loop documents | `loop-plan`, `LOOP.md` §6 |
| A stacked PR merged into another PR's branch, where nothing deploys, while GitHub reported it merged | Work believed shipped that never reached `main` | A concern counts as merged only if its merge commit is on `main`; loop-document PRs must target `main` | `loop-status` step 3, `check_loop_pr.sh` |

The common thread: **an agent will confidently extend whatever the document says.** So the method
treats every document as a hypothesis until the environment confirms it, and makes that confirmation
a named step rather than an afterthought. Generation 2 goes one step further: where a guardrail kept failing
because it relied on someone remembering, the state it guarded is no longer written down at all.
