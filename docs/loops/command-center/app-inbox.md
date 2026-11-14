---
needs: [app-shell, status-api, queue-items, app-clients]
touches: [app/src/app/(tabs)/inbox/, app/src/features/inbox/]
effects: [starting sessions that cost money; each card's dispatch names the person as sponsor and shows its budget before it starts (gates: spending)]
ships-to: staging/app-android
---
# The owner can finish a question, review, ship or record card from the phone's inbox

## Done when

- **C1** "Needs you" lists every item waiting on the signed-in person, sorted by how many concerns it unblocks.
  Each one is a card: question (options and recommendation, none pre-selected), review (evidence before the
  diff), ship (the brief and its manual steps) or record (the proposed text). The other three kinds of item
  show read-only, with the command to run (per command-center/D34). Items that wait on someone else
  show read-only to the loop's members (per command-center/D10). Prove: app tests against the status fixtures, in CI on main,
  and a recording on a device against staging.
- **C2** Finishing a card dispatches the matching skill through the runner, with the person as sponsor, and its
  write lands in `docs/loops/`. Answering a question records a `D#` through `/loop-design`. "Deployed" runs
  `/loop-ship` verification. Approving a record runs `/loop-status`'s record step. The person answers a question
  in the dispatched session's thread (per D3). Prove: one card of each kind on
  the sandbox loop (per command-center/D61), with the resulting commits, on staging.
- ~~**C3** A push notification goes out only for blocking items waiting on that person, and everything else waits
  for the digest. Prove: two accounts with one blocking and one non-blocking item, on staging.~~ Moved to
  `notifications` C2 (per command-center/D35).

## Design

### Where we are

- The design's Inbox, Question and Review artboards are the reference (per command-center/D4). Their supply-reality and
  objection cards, and the rule that comments must be answered before a merge, are out of this loop.
- Verified 2026-10-20 (`plugin/skills/loop-ship/SKILL.md` step 2): `/loop-ship` writes its brief in the promotion
  PR's body, or in chat when the project does not ship through PRs. Deploys here are commands the owner runs, not
  PRs, so a dispatched session has nowhere to leave the brief for the card yet (Q1).
- Verified 2026-10-20 (`plugin/skills/loop-status/SKILL.md`, "Record, on the owner's yes"): after the yes, the
  record step writes its PR and merges it itself under `LOOP.md` §2.1, so no one sees the text before it merges
  (Q2).
- Verified 2026-10-20 (`plugin/skills/loop-design/SKILL.md`, Boundary): decisions count only if the owner made them
  in the session's conversation, and the skill asks its questions one at a time. A dispatched session carries
  the answer only in its arguments (Q3).
- Proposal §5 (question card): a gated question needs a typed reason before it can be answered (Q4).
- Verified 2026-10-20 (the runner on main @a9fde89): a dispatch must name a concern and one of `loop-design`,
  `loop-build`, `loop-prove` and `loop-status`, so neither `/loop-ship` on an environment nor a loop's record step
  can be dispatched yet, and the runner keeps no session's final message. `runner-dispatch` C3 adds both (per D1,
  D2). Nothing in the runner posts to a thread yet; `session-narration` adds that and the relay of a member's
  reply into a running session (per D3). (Superseded in part, 2026-10-22, main @18b866b: PR #24 (900dc5a) built
  `runner-dispatch` C3, so `/loop-ship <environment>` and `/loop-status <loop>` can be dispatched, and the runner
  keeps each session's `final_message` and serves it with the session. Nothing in the runner posts to a thread
  yet.)
- Verified 2026-10-20 (`status.schema.json` on main @a9fde89): a record item carries the proposed text and its
  path (`record_detail`), which is what the record card shows (per D2).

### Approach

Screens follow the Inbox, Question and Review artboards. Merging a PR stays on the forge: the review card links
to it, because the app never merges (`LOOP.md` §2). A question card's recommendation is never pre-selected, and
the decision records who tapped it.

- **Ship card** (per D1): it dispatches `/loop-ship <environment>` and shows the brief, which is that session's
  final report, as the runner serves it. "Deployed" dispatches `/loop-ship`'s verification the same way.
- **Record card** (per D2): it shows the record item's proposed text from the status document, and approving
  dispatches the record step, which writes and merges its own PR under `LOOP.md` §2.1, as from a terminal.
- **Question card** (per D3): it dispatches `/loop-design` on the question's concern or loop, and opens that
  session's thread, where the skill asks the question and the person answers. The decision is the person's because
  they gave it in the session's conversation, which reaches the session through `session-narration`'s relay.
- **Gated questions** (per D4): when a question item's `gate` is set, the card asks for a typed reason before it
  sends the answer, and the reason goes into the decision's notes. A question's gate comes from the key its row
  names (per command-center/D60).
- **Ship items per gate** (per command-center/D59): a concern that crosses several gates has one ship item per
  gate, each waiting on that gate's holder with its own manual steps, plus one for `deploy`. The inbox shows each
  as its own card.
- **Threads and clients:** the question card opens the session thread at `/threads/sessions/[session]`, which
  `app-threads` serves (per command-center/D52). The runner's and threads' clients come from `app/src/api/` (per
  command-center/D55).

Per command-center/D51, this concern builds against the status schema's `waits_on`, `visible_to` and `gate` and the
runner and threads APIs, all on `main`. `addressed-to-people` and `session-narration` are not in `needs`, because
only C1's and C2's staging proofs rely on them, and those proofs wait until staging serves both.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |
| D1 | A dispatched `/loop-ship`'s brief is that session's final report. The runner keeps each session's final message and serves it with the session, and the ship card shows it. No change to `loop-ship` or to threads. | Juan, 2026-10-20 | Q1 |
| D2 | The record card shows what will be recorded, from the record item in the status document. Approving dispatches the record step as it is, and it merges its own PR. The person approves the proposed text, not the PR's exact diff. No skill changes. | Juan, 2026-10-20 | Q2 |
| D3 | A dispatched `/loop-design` asks its question in the session's thread, and the person answers there. No skill changes, but the question card needs `session-narration`'s relay of a member's message into a running session (its C2). | Juan, 2026-10-20 | Q3 |
| D4 | A gated question needs a typed reason before it can be answered, and the reason goes in the decision's notes. | Juan, 2026-10-20 | Q4 |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| ~~Q1~~ | ~~Where does a dispatched `/loop-ship` leave its brief, so the ship card can show it?~~ → D1 | | |
| ~~Q2~~ | ~~When does a person see a record's text, when the record step merges its own PR after the yes?~~ → D2 | | |
| ~~Q3~~ | ~~How does a dispatched `/loop-design` take the person's answer as theirs?~~ → D3 | | |
| ~~Q4~~ | ~~Is proposal §5's typed reason for gated questions in this loop?~~ → D4 | | |

## Evidence

- 2026-11-13 · C2 · CONTRADICTS · rung 1 · staging/app-android @d45ed2a · A record card's approval dispatches, and its write does not land. On the owner's Android phone with the preview APK against staging, during the G0 walkthrough, Needs you held two record cards once `app-environments` and `app-loops-board` were done on main 7a1ef4b (the served status document, 00:04 UTC on 2026-11-14), and the owner approved "Add a Shipped note to app-environments". The runner started session ba1b838 at 00:07:07 UTC: `loop-status` on loop `command-center`, holding no concern, sponsored by the owner, release v0.6.0, with the approval as its arguments. It ended `completed` 36 s after it started, having spent $0.09, with no branch, no pull request and no file changed. Its final message says why: inside the session the board read `app-environments` as `unknown`, because `sh scripts/gcp/served.sh` on the staging/app-android row failed, so it would not record a concern it could not see as done. Cause, read in `services/runner/Dockerfile` on 3e2e6d2, which staging/runner serves: the image installs `curl` to fetch a key and then runs `apt-get purge -y curl`, and `served.sh` reads every row with `curl`, so a session reads every staging row as unknown; session 3caa204 the same evening also reported that the served-commit checks failed. So no record card for a concern that ships above `main` can land from a runner session. One approval, so one sample. Not run: a question card, a review card and a ship card
- 2026-11-13 · C2 · CONTRADICTS · rung 1 · staging/app-android @d45ed2a · Re-run of the record card after PR #147 (ff82269) kept `curl` in the runner's image and the owner deployed it: staging/runner serves ff82269 (`served.sh`, 01:01 UTC on 2026-11-14). The cause named earlier today is fixed, and one gap is left. The owner approved "Add a Shipped note to app-environments" from the Android preview build again. Session b38044a (`loop-status` on loop `command-center`, sponsored by the owner, release v0.6.0) started at 00:59:00 UTC and ended `completed` 55 s later having spent $0.14. This time it read `app-environments` as `done`, wrote the note, and opened PR #148 from `docs/command-center-record-2026-11-14`: one file, under `docs/loops/`, its commit and its body carrying `Sponsored-by: jugonzal` and no `Concern:` line, and `check_loop_pr.sh --pr 148` passing. It did not merge it: its final message says the PR's checks had no result yet when it looked, and it ended. D2 says the record step "merges its own PR"; the checks took 2 min 34 s to finish, after the session was gone. The write landed in `docs/loops/` only when a terminal session, with the owner's `gh` sign-in, merged #148 as eb65fa2 at 01:06 UTC, once its six checks were green and `check_loop_pr.sh` had passed again. One run of this half, so one sample. The question card's half rests on the premise `app-documents` C2 contradicted today (a design session ends one second after it asks). Not run: a review card and a ship card

## Shipped
