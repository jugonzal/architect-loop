# A loop owner can run a whole loop from a phone, and a second person can hold a gate

**Intent.** Today the architect loop runs from one person's terminal. Each session shows one thing at a time and
forgets what it knew when it closes, and nobody else can see what is waiting on them. This loop builds the first
phase of the command center from [docs/proposals/command-center.md](../../proposals/command-center.md) (§8, phase 1
"Workbench, Charter, Roster"). That phase is a thin mobile app over a status service that derives every loop's
state the way `/loop-status` does, a runner that starts skills as sponsored sessions, and threads per loop and
concern. With it, the owner answers, reviews, ships and records from a phone, and a gate can belong to someone
other than the owner. Why now: the loop method is at generation 2 and stable, and the next limit is that only one
person in one terminal can push a loop forward.

**Non-goals.**
- The parts of the screen design that belong to later phases (per D4): supply-reality and objection cards,
  batons, comments that must be answered, delegated answers, replays, and the More tab (Charter, Commons,
  Retro). Each becomes its own loop through `/loop-plan` once this one is done.
- More than one project. Phase 1 serves `jugonzal/architect-loop` only, though it is built so more can be added
  (per D18).
- Any change to how a loop runs from a terminal, beyond what the status script adds (per D15). The skills always
  work alone, and someone who never opens the app loses nothing (per D14).
- The app editing files directly. It dispatches skills, and the skills write to the repository.
- Per-person metrics of any kind.
- A desktop or web client.

## Goals

- **G1** The owner runs one real loop in this repository from a phone, end to end. That means answering a
  question, reviewing a PR evidence-first, saying "deployed" on a ship card and approving a record card, all
  without a terminal. Each action lands in `docs/loops/` through its skill. Prove: a walkthrough on a real loop,
  with the resulting commits and PRs listed, using the production app build against production services.
- **G2** A concern whose `effects` cross a gate puts its card in the inbox of that gate's named holder, not the
  loop owner's, when they are different people. Other members of the loop see the card but cannot act on it
  (per D10). Prove: three signed-in accounts on staging (owner, gate holder, member), with a test concern that
  declares a gated effect.
- **G3** The app shows the same state as `/loop-status` for every concern in this repository, derived from the
  same commits, and shows `unknown` wherever `/loop-status` does (per D5). Prove: a comparison run over every
  concern in `docs/loops/` on production, with zero differences.
- **G4** The repository stays the brain. If the app's own store (threads, membership, sessions) is wiped, no
  state, decision or evidence shown for any loop changes. Prove: wipe the store on staging and re-run the G3
  comparison.

## Relations

- No other loop exists yet.
- **Home repository (per D13):** the skills, the method docs, the services and the app all live in
  [jugonzal/architect-loop](https://github.com/jugonzal/architect-loop). `one-repository` moves this loop there
  and makes the move safe, and every other concern needs it. All other concerns' `touches` are paths in
  architect-loop, and nothing is built in `jugonzal/loops`, which is archived once the move is done. Until then,
  only `one-repository` writes `architect-loop:` paths, because it is built while this loop still lives in loops.

## Where we are

- **Verified** (`git ls-files` on `main` @1748b7e, 2026-10-20): this repository holds only `LOOP.md`, the
  proposal, this loop and the vendored skills. There is no code, no CI and no environment beyond `main`.
  `LOOP.md` §3 and §4 are `TODO(owner)`.
- **Verified** (`.claude/skills/loop-status/SKILL.md`, steps 1 to 6): the derivation exists only as a table in
  prose. Its facts are git, `gh pr list`, served-commit commands and evidence lines. Its states are parked,
  contradicted, open, blocked, ready, building, merged, shipped, stale and done, plus unknown. Its queue is
  sorted by how many concerns each item unblocks. Nothing implements it as code. Upstream
  (`../architect-loop/tests/`) already tests its two scripts in Python (`test_check_loop_pr.py`,
  `test_migrate_gen1.py`), which is where the new script's tests go (per D15).
- **Verified** (the screen design canvas, https://claude.ai/artifact/2zWJ13odFUV1yNXkYR6urn, read 2026-10-20):
  eight 390×844 phone screens: Inbox, Question, Review, Concern, Loops, Session thread, Agents, Environments.
  There are five tabs: Needs you, Loops, Agents, Environments, More. The type is IBM Plex Sans and Mono. The
  state strip uses provisional, designing, ready, building, review, merged, proving, shipped, done and stale,
  which are not the derivation's states. Per D5 the app shows the derivation's states, so the strip has to be
  redrawn.
- **Verified** (`gcloud` and `amazonaws` references across `../vgami-cloud`, `../gameface` and
  `../nginx-config`, 2026-10-20): the owner already runs services on GCP and AWS. Per D8 this loop uses GCP.
- **Verified** (`gh repo view jugonzal/architect-loop`, `git log`, `diff -rq`, 2026-10-20): architect-loop is
  private, MIT, with 0 forks and 21 commits since 2026-10-01. Its CI is `.github/workflows/check.yml`, which runs
  `scripts/check.sh` and its unittest suite. Its plugin installs from the repository root
  (`.claude-plugin/marketplace.json`: `"source": "./"`), so anything added at the root would ship with every
  install, which is why D16 moves the skills to `plugin/`. Its `skills/` folder is identical to this
  repository's `.claude/skills/`. Its copy of `docs/proposals/command-center.md` is identical to this one, but
  uncommitted. It has no `LOOP.md` and no `docs/loops/`.
- **Assumed:** the Claude Agent SDK can run a skill in a container with its own worktree, report its token and
  money cost, and stop at a budget. This is the riskiest unknown in the loop. Check it with the spike in
  `session-runner` Q1.
- **Missing:** `LOOP.md` §3 rows for staging and production, with a `/version` URL for each service (per D8, D9).
  `status-service` adds them, and the owner merges that change.

## Shared decisions

| # | Decision | Decided by, date | Notes |
| --- | --- | --- | --- |
| D1 | The command center is option C: a thin app over a status service and a runner, with threads as the only store it owns. | Juan, 2026-10-20 | Closes Q1 |
| ~~D2~~ | ~~The derivation is a script upstream in architect-loop, `skills/loop-status/scripts/loop_status.py`, with fixture tests there. The skill keeps its table as the specification. The terminal and the status service run the same script.~~ | Juan, 2026-10-20 | Closes Q5; superseded by D15, 2026-10-20 |
| ~~D3~~ | ~~Phase 1 serves one project, `jugonzal/loops`. Every API and store is keyed by project, so more can be added later.~~ | Juan, 2026-10-20 | Closes Q8; superseded by D18, 2026-10-20 |
| D4 | The screen design canvas (https://claude.ai/artifact/2zWJ13odFUV1yNXkYR6urn) is the reference for the app's screens, navigation and look. This loop builds the phase 1 slice of it: the Inbox with question, review, ship and record cards; Loops; Concern; concern and session threads; Agents; Environments. Its other elements are later loops. | Juan, 2026-10-20 | Closes Q9 |
| D5 | The app shows exactly the states the derivation produces. Finer detail ("in review", "proving") is the state's reason line, never a state of its own. | Juan, 2026-10-20 | Closes Q10 |
| D6 | Threads live in the app's own store. Review comments on a concern's PR are mirrored into its concern thread. | Juan, 2026-10-20 | Closes Q2 |
| D7 | The mobile app is React Native with Expo, in TypeScript, using Expo push and EAS builds for TestFlight and Play internal testing. | Juan, 2026-10-20 | Closes Q6 |
| D8 | Services run on GCP: Cloud Run for the status service, the runner and the thread API, and Cloud SQL for the thread store. Staging and production are separate. Each service reports the commit it runs at a `/version` endpoint. | Juan, 2026-10-20 | Closes Q7 |
| D9 | The status service reads each environment's served commit only by an HTTP GET of a URL listed in `LOOP.md` §3. It never runs a shell command taken from the repository. The terminal `/loop-status` still runs commands locally. | Juan, 2026-10-20 | Closes Q11 |
| D10 | Each loop has one owner, its architect. Co-ownership exists only through delegation: other members act on an answer or action only when the owner delegates it, and until then they see it read-only. Batons coordinate delegated work in a later loop. | Juan, 2026-10-20 | Closes Q3 |
| ~~D11~~ | ~~The status JSON schema lives upstream beside the script, and the script's `--json` output is versioned with it. This repository generates TypeScript types from the copy at a pinned commit.~~ | Juan, 2026-10-20 | Closes Q12; superseded by D15, 2026-10-20 |
| ~~D12~~ | ~~The `owner:` and `members:` front matter, the gate-holder names in `LOOP.md` §2 and the addressing logic go upstream with the derivation, so the terminal `/loop-status` also shows who each item waits on.~~ | Juan, 2026-10-20 | Closes Q13; superseded by D15, 2026-10-20 |
| D13 | The skills and the command center live in one repository and evolve together, so one PR can change a format, its derivation, its schema and the screen that shows it. Home is `jugonzal/architect-loop`. `LOOP.md` and `docs/loops/` move there, and `jugonzal/loops` is archived. | Juan, 2026-10-20 | Closes Q14, Q15 |
| D14 | Running the loop from a terminal stays first-class: the skills always work alone. Nothing under the skills folder reads, calls or assumes the app or the services, and the app and services read only what the skills write. CI enforces it. | Juan, 2026-10-20 | Closes Q16 |
| D15 | The derivation is one script, `plugin/skills/loop-status/scripts/loop_status.py`, run by both the terminal and the status service, with fixture tests in `tests/`. The skill keeps its table as the specification. The status JSON schema sits beside the script and is versioned with its `--json` output. The `owner:`/`members:` front matter, the gate-holder names in `LOOP.md` §2 and the addressing logic live with the derivation. This restates D2, D11 and D12 for the one repository (per D13). | Juan, 2026-10-20 | Supersedes D2, D11, D12 |
| D16 | The skills are packaged under `plugin/` (`plugin/.claude-plugin/plugin.json` and `plugin/skills/`), and the marketplace's source is `./plugin`, so installing the plugin ships only the skills. `install.sh` copies from there. | Juan, 2026-10-20 | Closes Q17 |
| D17 | Changes to the skills are ordinary concerns that the owner reviews and merges. Cutting a release (version bump, tag, marketplace update) is the owner's alone. Agents always work with an installed release of the skills, never the working-tree skills they are editing. | Juan, 2026-10-20 | Closes Q18 |
| D18 | Phase 1 serves one project, `jugonzal/architect-loop`, the home per D13. Every API and store is keyed by project, so more can be added later. | Juan, 2026-10-20 | Supersedes D3 |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| ~~Q1~~ | ~~Adopt option C, A or B? (proposal §7)~~ → D1 | | |
| ~~Q2~~ | ~~Where do threads live? (proposal Q1)~~ → D6 | | |
| ~~Q3~~ | ~~One owner per loop, or co-owners? (proposal Q2)~~ → D10 | | |
| ~~Q4~~ | ~~Which runner? (proposal Q3)~~ → moved to `session-runner` Q1, a spike | | |
| ~~Q5~~ | ~~Does the derivation live in a script? (proposal Q5)~~ → D2 | | |
| ~~Q6~~ | ~~Which mobile stack?~~ → D7 | | |
| ~~Q7~~ | ~~Where do the services run, and how does each report its commit?~~ → D8 | | |
| ~~Q8~~ | ~~One project or many in phase 1?~~ → D3 | | |
| ~~Q9~~ | ~~Which of the screen design's screens are in this loop, and do threads stay?~~ → D4 | | |
| ~~Q10~~ | ~~The design's state names, or the derivation's?~~ → D5 | | |
| ~~Q11~~ | ~~May the service run `LOOP.md`'s served-commit shell commands?~~ → D9 | | |
| ~~Q12~~ | ~~Where does the status schema live?~~ → D11 | | |
| ~~Q13~~ | ~~Do the people fields and the addressing logic go upstream?~~ → D12 | | |
| ~~Q14~~ | ~~One repository for the skills and the command center, or two?~~ → D13 | | |
| ~~Q15~~ | ~~If one, which repository is home?~~ → D13 | | |
| ~~Q16~~ | ~~Does running from a terminal stay first-class?~~ → D14 | | |
| ~~Q17~~ | ~~How are the skills packaged so plugin installs do not ship the app?~~ → D16 | | |
| ~~Q18~~ | ~~How are changes to the skills gated once they are ordinary code?~~ → D17 | | |

## Evidence

## Shipped
