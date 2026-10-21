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
- **G4** The repository stays the brain. If the command center's stores (the threads, the runner's sessions,
  the notifier's devices and settings) are wiped, no state, decision or evidence shown for any loop changes
  (per D26). Prove: wipe every store on staging and re-run the G3 comparison.

## Relations

- No other loop exists yet.
- **Home repository (per D13):** the skills, the method docs, the services, the app and this loop all live in
  [jugonzal/architect-loop](https://github.com/jugonzal/architect-loop). `one-repository` moved the loop here and
  makes the move safe, and every other concern needs it. Every concern's `touches` are paths in this repository.
  `one-repository`'s `architect-loop:` prefixes name this same repository: they date from when it was built from
  `jugonzal/loops`, which the owner archives once the move is done. Nothing is built there. (Corrected
  2026-10-20: this said the loop still lived in `jugonzal/loops`.)

## Where we are

- **Verified** (`git ls-tree` on `main` @355dcb7, 2026-10-20): this repository holds the skills under `plugin/`,
  the method docs, `LOOP.md`, the proposals, this loop, `scripts/`, `tests/` and CI (`check`). There is no `app/`
  or `services/` yet, and no environment beyond `main`. In `LOOP.md`, the staging and production rows of §3 and
  the smoke test and deploy commands of §4 are `TODO(owner)`. (Corrected 2026-10-20: this bullet described
  `jugonzal/loops` before the move.) (Superseded by the next bullet, 2026-10-20: `services/` and the §3 rows
  now exist.)
- **Verified** (`git ls-tree` and `LOOP.md` on `main` @a9fde89, 2026-10-20): `services/runner/` (PR #20) and
  `services/threads/` (PR #21) exist, with their workflows `runner.yml`, `threads.yml` and `trailers.yml`, and
  `scripts/gcp/` holds the bootstrap, deploy and probe (PR #19). There is no `app/`. `LOOP.md` §3 has one row per
  service and environment (`staging/runner`, `production/threads`, ...) and no row named `staging` or
  `production`, so `ships-to: production` matched no row (D43 fixes it). Every row's URL, and both project IDs in
  `scripts/gcp/projects.txt`, are `TODO(owner)` until the owner runs the bootstrap. The smoke test in §4 is still
  `TODO(owner)`. Each service reads its commit from `COMMIT_SHA`, which `deploy.sh` sets (per D47), and
  `deploy.sh` changes nothing else in a service's config (D46 changes that).
- **Verified** (`plugin/skills/loop-status/SKILL.md`, steps 1 to 6): the derivation exists only as a table in
  prose. Its facts are git, `gh pr list`, served-commit commands and evidence lines. Its states are parked,
  contradicted, open, blocked, ready, building, merged, shipped, stale and done, plus unknown. Its queue is
  sorted by how many concerns each item unblocks. Nothing implements it as code. `tests/` already tests its two
  scripts in Python (`test_check_loop_pr.py`, `test_migrate_gen1.py`), which is where the new script's tests go
  (per D15). The table has no rule for a pull request merged in another repository, and runs on the same facts
  returned different boards (`one-repository` C3, 2026-10-20). D19 adds the rule. (Paths corrected 2026-10-20 for
  the move.)
- **Verified** (the screen design canvas, https://claude.ai/artifact/2zWJ13odFUV1yNXkYR6urn, read 2026-10-20):
  eight 390×844 phone screens: Inbox, Question, Review, Concern, Loops, Session thread, Agents, Environments.
  There are five tabs: Needs you, Loops, Agents, Environments, More. The type is IBM Plex Sans and Mono. The
  state strip uses provisional, designing, ready, building, review, merged, proving, shipped, done and stale,
  which are not the derivation's states. Per D5 the app shows the derivation's states, so the strip has to be
  redrawn.
- **Verified** (`gcloud` and `amazonaws` references across the owner's other repositories, 2026-10-20): the
  owner already runs services on GCP and AWS. Per D8 this loop uses GCP. Of the 7 GCP region names in those
  repositories, 6 are `us-east1` (per D32). (Corrected 2026-10-20: this bullet named those repositories, which
  this repository keeps out of new text, per D25.)
- **Verified** (`gh repo view jugonzal/architect-loop`, 2026-10-20): architect-loop is public and MIT (per D24).
  Its CI is `.github/workflows/check.yml`, which runs `scripts/check.sh` and its unittest suite. (Corrected
  2026-10-20: this said the repository was private, which it was until the owner carried out D24.)
- **Verified** (`gh api repos/jugonzal/architect-loop/rulesets/<id>`, 2026-10-20): `main` is protected by an
  active ruleset, "main", with no bypass actors. It blocks deletion and force pushes, requires a pull request
  (no approvals), and requires the `skills` check. `trailers` joins it once `session-runner` adds the workflow
  (per D24). (Checked again on main @a9fde89, 2026-10-20: `trailers.yml` exists since PR #20, and the ruleset
  still requires only `skills`; making `trailers` required is the owner's, in `session-runner`'s effects.) (Corrected 2026-10-20: this said `main` had no protection. While the repository was private, both
  the branch protection and the rulesets APIs answered 403, "Upgrade to GitHub Pro or make this repository public
  to enable this feature", and that is why it went public.)
- **Verified** (`git log --all -p`, `gh pr list` bodies, and every PR's issue and review comments, 2026-10-20):
  before publishing, the only mentions of the owner's private projects are in one old diff (44893df) and in
  PR #1's body. Both stay as they are (per D25).
- **Verified** (GitHub's docs, https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/using-webhooks-with-github-apps,
  read 2026-10-20): a GitHub App registration has one webhook URL, so services that each need webhooks each get
  their own app (per D27).
- **Verified** (`git tag -l`, `plugin/.claude-plugin/plugin.json`, and `gh repo view jugonzal/loops`,
  2026-10-20): release v0.3.0 is tagged at fbd6d0b, the plugin is 0.3.0, and `jugonzal/loops` is archived, so
  `one-repository`'s remaining effects are done. `session-runner`'s job can install v0.3.0. (Corrected 2026-10-20:
  this said no release was tagged, the plugin was 0.2.0, and `jugonzal/loops` was not archived.)
- **Verified** (`one-repository`'s evidence, main @4e7bf9a, 2026-10-20): the marketplace serves `./plugin`, and a
  real install from `main` ships only `plugin/` (C1). CI fails on any reference to `app/` or `services/` under
  `plugin/` (C2). Adding the marketplace clones the whole repository into the user's plugin config, but nothing
  outside `plugin/` loads from it (per D20). (Corrected 2026-10-20: this bullet described architect-loop before
  the move, when the marketplace served the repository root.)
- **Verified** (`session-runner` Q1, the spike, rung 3, 2026-10-20): the Claude Agent SDK runs a loop skill in a
  container on its own fresh clone, from an installed plugin. It reports tokens, a client-side cost estimate and
  time, and stops at a budget, though only after the response that crosses it. (Corrected 2026-10-20: this was
  the loop's riskiest assumption.)
- **Verified** (GitHub's docs, https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps,
  read 2026-10-20): the web flow's token exchange requires the OAuth app's client secret, with or without PKCE.
  The device flow needs no secret, and must be enabled in the app's settings (`app-shell` D1).
- **Verified** (GitHub's docs, https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app,
  read 2026-10-20): an installation token expires after 1 hour, and can be limited to chosen repositories and
  permissions when it is minted (`session-runner` D7).
- **Verified** (the runner on `main` @a9fde89, 2026-10-20): every session adds `Concern:` to its commits and PR
  bodies whatever its skill (D45 changes that). A dispatch must name a concern and one of `loop-design`,
  `loop-build`, `loop-prove` and `loop-status`, so `/loop-ship` and a loop's record step cannot be dispatched.
  An open PR or a running session refuses every skill on its concern. Any positive budget is accepted. The only
  store is SQLite, which the service and its jobs, in separate containers, cannot share (D44). The job holds the
  app's private key. Nothing in the job posts to a thread. `runner-dispatch` and `runner-store` build the changes,
  and `session-narration` the threads.
- **Missing:** `LOOP.md` §3 rows for staging and production, with a `/version` URL for each service (per D8, D9).
  `environments` adds them, and the owner merges that change (per D31). (Corrected 2026-10-20: this said
  `status-service` adds them.) (Corrected 2026-10-20: PR #19 added the rows; only their URLs are missing, until
  the owner runs the bootstrap.)

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
| D19 | A concern's pull request that merged in another repository counts as merged when its merge commit is on that repository's main, and for `ships-to: main`, that main serves it. The derivation table in `loop-status` gains this rule, and the derivation script a fixture for it. | Juan, 2026-10-20 | Closes Q19 |
| D20 | Adding the marketplace may clone the whole repository into each user's plugin config, since nothing outside `plugin/` loads from it. Accepted for now. Revisit once `app/` lands, if its size matters, for example by documenting `claude plugin marketplace add jugonzal/architect-loop --sparse .claude-plugin plugin` (tested 2026-10-20). | Juan, 2026-10-20 | Closes Q20 |
| D21 | A session's budget is a target it may pass by one model response. The SDK stops a session at the first response that crosses its budget, and the runner reports its estimated spend, overshoot included. | Juan, 2026-10-20 | Closes Q21 |
| D22 | A sponsor may run at most 3 sessions at once. The cap is set in the runner's config, and a dispatch past it is refused, naming the running sessions. | Juan, 2026-10-20 | Closes Q22 |
| D23 | The runner publishes each session's spend while it runs (approximate, from per-step usage, at least every 10 seconds) and at the end (the SDK's estimate). Before a start, it estimates a skill on its model as the median of that pairing's last 10 sessions, and a pairing with none has no estimate. Every figure is labelled as an estimate. | Juan, 2026-10-20 | Closes Q23 |
| D24 | The repository becomes public so that `main` can be protected: changes reach it only through pull requests, with `check` required now and `trailers` once `session-runner` adds it, for admins too. The owner makes it public and sets the protection. This was chosen over GitHub Pro (about $4 a month, a third-party 2026 figure) and over a push proxy in the runner. | Juan, 2026-10-20 | Closes Q24 |
| D25 | It is published as it is. PR #1's body and one old diff (44893df) keep the mentions of the owner's private projects they have, and history is not rewritten, since every evidence line cites a commit on `main`. New text keeps the owner's private projects out. | Juan, 2026-10-20 | Closes Q25 |
| D26 | Each service keeps its own operational store: the runner its sessions and spend, `notifications` its devices and settings. The thread store keeps only what people write. No store holds a loop's state, and G4's wipe covers every store. | Juan, 2026-10-20 | Closes Q26; refines D1, whose thread store stays the only store of what people write |
| D27 | Each service has its own GitHub App, with only the permissions it needs. The runner's app pushes branches and opens pull requests. The status service's and threads' apps only read, and each receives its own webhooks. Each app's key and webhook secret live in that environment's Secret Manager. | Juan, 2026-10-20 | Closes Q27 |
| D28 | The app's sign-in asks GitHub for no repository access, so its token proves who the person is and nothing more. Each service identifies a caller with `GET /user` on the caller's token, and checks collaborator access with its own app (per D27). Every repository read goes through a service. Calls between services use Cloud Run's service identity. | Juan, 2026-10-20 | Closes Q28 |
| D29 | Each service publishes its API as an OpenAPI file in its own folder (`services/<name>/openapi.yaml`), checked by one of its claims. Each app concern generates the clients it needs inside its own `features/` folder. `app-shell` provides only the signed-in fetch and the status client. | Juan, 2026-10-20 | Closes Q29 |
| D30 | The services are Python 3.12, each with its own dependencies and its tests in `services/<name>/tests/`. The app and each service run their tests in their own workflow, `.github/workflows/<name>.yml`, which is in that concern's `touches`. The root `check` stays standard-library only. | Juan, 2026-10-20 | Closes Q30 |
| D31 | A new concern, `environments`, owns the GCP projects, the deploy command and the `LOOP.md` §3 and §4 rows. The services do not need it: they build against D32 now and stay merged until staging exists. `status-service` no longer creates the projects, and no service edits `LOOP.md`. | Juan, 2026-10-20 | Closes Q31 |
| D32 | Every service follows one convention. It runs in `us-east1`. It builds from `services/<name>/Dockerfile` with the repository root as context. It listens on `$PORT` and serves an unauthenticated `GET /version` answering `{"commit": "<sha>"}`. It reads config from environment variables and secrets from Secret Manager. The owner deploys it from a commit on `main` with one command. | Juan, 2026-10-20 | Closes Q32 |
| D33 | Every open question records, in the file that raises it, 2 to 4 options with each one's main consequence, and a recommendation. A new concern, `question-options`, defines the format and a reader for it. The status schema carries the options, and a question written before the format shows only the question, what it blocks and its default. | Juan, 2026-10-20 | Closes Q33 |
| D34 | The status schema carries all seven kinds of queue item that `/loop-status` step 6 produces: question, review, ship, record, a proof that needs something only the person has, a contradiction that needs a call, and a refused loop-document PR. The app has cards for the first four and shows the other three read-only, with the command to run. | Juan, 2026-10-20 | Closes Q34 |
| D35 | Push and the digest are a new concern, `notifications`, with its own service and store (per D26). It takes over push registration from `app-shell` (C2) and sending from `app-inbox` (C3). | Juan, 2026-10-20 | Closes Q35 |
| D36 | A person marks a message "record this?". No model reads messages to classify them. | Juan, 2026-10-20 | Closes Q36 |
| D37 | A loop's state can be `unknown`, when a fact its state depends on cannot be read, and it is never guessed as active. Step 5 of the `loop-status` table gains this, and `status-derivation` writes it. | Juan, 2026-10-20 | Closes Q38 |
| D38 | Each queue item carries `gate`: the `LOOP.md` §2 gate it crosses, or null. `addressed-to-people` routes an item to that gate's holder by it (G2). | Juan, 2026-10-20 | Closes Q39 |
| D39 | The three missing queue kinds and D33's options move to a new concern, `queue-items`, which needs `status-api` and works in its three paths. `status-api` keeps what PR #11 delivered (its C3); its C1 is split. The concerns that read queue items need `queue-items`: `status-derivation`, `addressed-to-people`, `status-service`, `app-shell` and `app-inbox`. | Juan, 2026-10-20 | Closes Q40 |
| D40 | The three read-only kinds each carry the command to run and their facts. A proof names the claim, the environment, what is missing and who can supply it. A contradiction names the claim, its CONTRADICTS line, what it contradicts and whether it escalates to the loop. A refused loop-document PR names the PR and the checker's failure lines. | Juan, 2026-10-20 | Closes Q41 |
| D41 | A question item's options are each a text with its consequence. Its recommendation names one option or is null, and its default is the table's "Default if unanswered", kept apart. A question written before the format has no options and no recommendation. `question-options`' reader returns this shape. | Juan, 2026-10-20 | Closes Q42 |
| D42 | A concern's `needs` lists the concerns its build relies on whose work is not on `main` yet, and any concern not on `main` yet whose `touches` it shares. Once a needed concern's work is on `main`, the consumer builds against it there, and its proofs on an environment wait until that environment serves the need. Needs that are already done may stay. On 2026-10-20 this drops `session-runner`, `threads`, `question-options` and `environments` from the needs of the concerns that had them. | Juan, 2026-10-20 | Closes Q43 |
| D43 | A concern's `ships-to` names the `LOOP.md` §3 row that serves its work: `production/<service>` for a service, `production/app` for the app (a row that `app-shell` adds, with how a build reports its commit), and `main` for scripts and skills. A claim whose Prove names staging is proven on `staging/<service>` first and then on its production row, and only the production line counts toward done. `environments` ships to `main`: its work is scripts the owner runs from `main`, and its proofs cite the commit they ran from. | Juan, 2026-10-20 | Closes Q44 |
| D44 | The runner's and `notifications`' operational stores are Firestore, each service in a database of its own in its environment's project (per D26). The thread store stays Cloud SQL Postgres (per D8). | Juan, 2026-10-20 | Closes Q45; refines D8 |
| D45 | Only a `/loop-build` session's commits and PR carry `Concern:`. Every runner session's commits and PRs carry `Sponsored-by:`. This matches how design, proof and record commits are written from a terminal, so `/loop-status` never counts them as build work. | Juan, 2026-10-20 | Closes Q46; rewords `session-runner` C1 |
| D46 | Each service's deploy config lives in a manifest in its own folder: its non-secret settings, the names of its secrets, its Cloud SQL instance, its runtime identity, its jobs and the APIs it needs. `deploy.sh` applies it on every deploy, so the config is reviewed in pull requests and rolls back with the code, and `bootstrap.sh` enables the APIs and creates what the manifests declare. `service-manifests` builds this for the runner and threads, and each later service adds its own manifest. | Juan, 2026-10-20 | Closes Q47 |
| D47 | Every service reads the commit it runs from the environment variable `COMMIT_SHA`, which `deploy.sh` sets. | Juan, 2026-10-20 | Closes Q48; refines D32; confirms PRs #19, #20 and #21 |
| D48 | Every service's API keys a project as `{owner}/{repo}` in its paths, as threads does (`/projects/{owner}/{repo}/...`). The status service serves `/projects/{owner}/{repo}/status`. | Juan, 2026-10-20 | Closes Q49; refines D18; confirms PR #21 |

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
| ~~Q19~~ | ~~How does the derivation count a concern's pull request that merged in another repository? (raised by `one-repository` C3)~~ → D19 | | |
| ~~Q20~~ | ~~Does the marketplace's full clone of the repository need fixing now?~~ → D20 | | |
| ~~Q21~~ | ~~What may a sponsor rely on when a session reaches its budget? (raised by `session-runner` Q1)~~ → D21 | | |
| ~~Q22~~ | ~~How many sessions may one sponsor run at once? (left to the runner by `app-agents`)~~ → D22 | | |
| ~~Q23~~ | ~~What spend does the runner publish, and where do estimates come from?~~ → D23 | | |
| ~~Q24~~ | ~~How is `main` protected, when this plan cannot protect a private repository's branches? (raised by this design's read of GitHub, 2026-10-20)~~ → D24 | | |
| ~~Q25~~ | ~~What happens, before publishing, to the existing mentions of the owner's private projects?~~ → D25 | | |
| ~~Q26~~ | ~~Where do the runner's sessions and spend history live, when D1 makes threads the only store?~~ → D26 | | |
| ~~Q27~~ | ~~How many GitHub Apps, when each has one webhook URL?~~ → D27 | | |
| ~~Q28~~ | ~~How do services know who is calling, and what may the app's sign-in token do?~~ → D28 | | |
| ~~Q29~~ | ~~Where are the runner's and the threads' APIs defined?~~ → D29 | | |
| ~~Q30~~ | ~~What are the services built with, and where do their tests and the app's run?~~ → D30 | | |
| ~~Q31~~ | ~~Who owns the GCP projects, the deploy command and `LOOP.md` §3?~~ → D31 | | |
| ~~Q32~~ | ~~Which convention do the services build and deploy by?~~ → D32 | | |
| ~~Q33~~ | ~~Where do a question card's options and recommendation come from?~~ → D33 | | |
| ~~Q34~~ | ~~Which kinds of queue item does the status schema carry?~~ → D34 | | |
| ~~Q35~~ | ~~Who keeps devices and sends push and the digest?~~ → D35 | | |
| ~~Q36~~ | ~~Who decides that a thread message looks like a decision?~~ → D36 | | |
| ~~Q37~~ | ~~Does D34 stand against PR #11's five kinds, where a contradiction is a question and a refused loop-document PR is a review? (raised by `status-api`'s build)~~ → D34 stands (Juan, 2026-10-20) | | |
| ~~Q38~~ | ~~Can a loop's state be `unknown`? (raised by `status-api`'s build)~~ → D37 | | |
| ~~Q39~~ | ~~Does a queue item carry the gate it crosses? (raised by `status-api`'s build)~~ → D38 | | |
| ~~Q40~~ | ~~How does the schema catch up with D33 and D34, now that PR #11 merged with four kinds and plain options? (raised by `status-api`)~~ → D39 | | |
| ~~Q41~~ | ~~What do the three read-only kinds of queue item carry?~~ → D40 | | |
| ~~Q42~~ | ~~How does a question item carry its options, recommendation and default?~~ → D41 | | |
| ~~Q43~~ | ~~When does a concern's `needs` count as met, when the services it needs ship to an environment that does not exist yet? (raised by the board after PRs #18 to #21 merged)~~ → D42 | | |
| ~~Q44~~ | ~~What does `ships-to` name, now that `LOOP.md` §3 has one row per service and none named `production`? (raised by `environments`' build)~~ → D43 | | |
| ~~Q45~~ | ~~Which database backs the runner's store, when its service and jobs cannot share SQLite? (raised by `session-runner`'s build)~~ → D44 | | |
| ~~Q46~~ | ~~Which runner sessions add `Concern:` to their commits and PRs? (raised by `session-runner`'s build)~~ → D45 | | |
| ~~Q47~~ | ~~Where does each service's deploy config live? (raised by `environments`' and `threads`' builds)~~ → D46 | | |
| ~~Q48~~ | ~~Which environment variable carries a service's commit? (raised by `environments`' build)~~ → D47 | | |
| ~~Q49~~ | ~~How does a service's API name a project in its paths? (raised by `threads`' build)~~ → D48 | | |

## Evidence

## Shipped
