---
needs: []
touches: [app/package.json, app/src/app/(tabs)/loops/, app/src/features/loops/]
effects: [starting sessions that cost money; the person sees the estimate and the budget and confirms each start (gates: spending)]
ships-to: staging/app-android
---
# A loop's owner can read the document behind any loop or concern on the phone, and start a design session from it

## Done when

- **C1** A concern page and a loop page show their own document, rendered, as it stands at the main commit the
  status document was gathered on, and say which commit that is. When the file cannot be read, the page says so
  and still shows the derived state. Prove: app tests against the status fixtures and a fake GitHub, in CI on
  main, and a device check against staging that compares the page with `git show <sha>:<path>` for
  `sandbox/design-target` and one command-center concern.
- **C2** A concern page and a loop page can start `/loop-design` on that concern or loop, naming no question, with
  the estimate, the budget and the release shown first as on every start sheet (per D68), and then open the
  session's thread. A concern the runner refuses (an open PR, or a session already running on it) shows the
  refusal and the session already running. Prove: app tests in CI on main, and on staging, a start from
  `sandbox/design-target`'s page whose session asks in its thread and is answered there.

## Design

### Where we are

- Verified 2026-10-27 (main @20db0c4): the status document names each loop's and concern's `path` and
  `main.sha`, so the app already has what it needs to find the file at the derived commit. The repository is
  public, so the sign-in token, which asks for no repository access (`app-shell` D1), can read it. The start
  sheet, its estimate and the dispatch are in `app/src/features/inbox/` (`StartSheet.tsx`, `dispatch.ts`), and
  the thread screen is at `/threads/sessions/[session]`.

### Approach

This builds the reading half of G0 (per D71, D72). The concern and loop pages read
`GET /repos/{owner}/{repo}/contents/{path}?ref={main.sha}` with the person's token and render the markdown below
the derived state, which stays first. Reading at `main.sha` rather than the branch tip keeps the text and the
state from the same commit. The design start reuses the inbox's start sheet and dispatch without editing them. It
adds a plan for `/loop-design` on a concern or a loop with empty arguments, beside `answerPlan`, in this concern's
own folder. `needs` is empty: the screens it extends are on main, and their own proofs (`app-loops-board`,
`app-inbox`) do not gate building this one. A private project would need a token with read access to contents,
which is `app-shell`'s sign-in scope and out of scope here (phase 1 serves this public repository only, per D18).

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

- 2026-11-13 · C2 · CONTRADICTS · rung 1 · staging/app-android @d45ed2a · The start holds and the answer cannot happen. On the owner's Android phone with the preview APK, signed in against staging, during the G0 walkthrough; the installed build is taken to be the latest finished preview build, which the row serves (`served.sh`, d45ed2a), the owner started `/loop-design` from `sandbox/design-target`'s page: the sheet showed the command, the sponsor, a $2.00 budget, "No estimate yet" and "Runs the skills released as v0.6.0, the newest release"; the runner answered `POST /sessions` 201 at 23:46:04 UTC (session 3caa204, `loop-design`, `sandbox/design-target`, release v0.6.0), and the app read the session and its thread at 23:46:06. The session posted its question (Q1, both options, a recommendation) to its thread at 23:47:20 and its Finished milestone at 23:47:21, 51 s after it started, with $0.23 spent and no pull request. So the Prove's "whose session asks in its thread and is answered there" cannot be met: the person has one second to answer. Cause, read in `services/runner/runner/session.py` on 3e2e6d2, which staging/runner serves: the Stop hook relays only messages already in the thread and waits for none. This contradicts `app-inbox` D3's premise that the relay of `session-narration` C2 is enough for a design session to be answered in its thread; the question card of `app-inbox` C2 rests on the same premise. One session, so one sample. Also seen: back on the page the sheet still showed its spinner at 23:53, seven minutes after the start (`DesignStart.tsx` never clears `starting` once a start succeeds), and the runner's log has no second `POST /sessions`

## Shipped
