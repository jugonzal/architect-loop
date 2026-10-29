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

## Shipped
