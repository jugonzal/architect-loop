# Proposal: Let users export their widgets

**Status:** In progress — 2026-09-30. Steps 0 and 1 are done on production; the admin view and
the progress bar are open.
**Area:** `src/`
**Revisions:** —

## 0. Summary

Users cannot get their widgets out of the app. This adds a CSV export, then moves it off the
request path.

## 1. Where we actually are

- Nothing exports today.

## 2. Goals and gates

- **G1** A user downloads every widget as CSV, verified on production.
- **G2 Fast.** The export of 1000 widgets takes under 2 s.
  Measured on staging, 20 runs.

Non-goals: importing widgets back.

## 6. Decisions

| # | Decision | Decided by, date | Notes |
| --- | --- | --- | --- |
| D1 | CSV, not JSON | owner, 2026-09-20 | Closes Q1 |
| ~~D2~~ | ~~Export synchronously~~ → D3 | owner, 2026-09-21 | |
| D3 | Export through the job queue | owner, 2026-09-22 | Supersedes D2 |

## 7. Open questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| ~~Q1~~ | ~~CSV or JSON?~~ → D1 | | |
| Q2 | Include deleted widgets? | Step 4 | No |

## 8. Defaults this plan assumes, veto any

- The file name carries the date.
- Exports expire after 7 days.

## 9. Plan

### Step 0 — Spike the CSV writer

- **Does:** answers Q1.
- **Done when:** a 1000-row file is written in under 1 s on a laptop.
- **Gate:** none.
- **Status:** done, 2026-09-21
- **Proof:** HOLDS (rung 4, local, 2026-09-21): 0.4 s for 1000 rows.

### Step 1 — Add the export endpoint (per D1)

- **Does:** adds `GET /export`.
- **Done when:** a user downloads a CSV on production.
- **Gate:** none to build; the owner deploys.
- **Status:** built, merged #12; on staging (`{SHA12}`) and production (`{SHA12}`), verified 2026-09-28
- **Proof:** HOLDS on production (rung 1, `{SHA12}`, 2026-09-28): the download worked.

### Step 2 — The admin view

*Split into 2a and 2b on 2026-09-29.*

#### Step 2a — List the exports (D1)

- **Does:**
  - adds an Exports screen to the admin;
  - shows each export's size.
- **Done when:**
  - the screen lists every export of the last 7 days;
  - an admin sees the size of each.
- **Gate:** none.
- **Status:** built, merged #14; on staging (`{SHA14}`), verified 2026-09-29; not yet on production
- **Proof:** HOLDS on staging (rung 1, `{SHA14}`, 2026-09-29): the list shows 3 exports. UNPROVEN: the sizes, which need a real export.

#### Step 2b — Cancel an export

- **Does:** a Cancel button.
- **Done when:** a cancelled export never finishes.
- **Gate:** none.
- **Status:** not started
- **Proof:** the owner clicked it once on a laptop and it looked fine.

### Step 3 — Show progress in the UI (after Step 2a)

- **Does:** a progress bar while the export runs.
- **Done when:** the bar reaches 100% when the file is ready.
- **Gate:** none.
- **Status:** in progress on `feat/progress` (#15)
- **Proof:** UNPROVEN (2026-09-30): no build yet.

### Hardening track

These steps can run after the export ships.

### Step 4 — Export in the background (after Step 1; D3)

- **Does:** moves the export onto the job queue.
- **Gate:** **migration on shared data (owner).**
- **Status:** not started
- **Proof:** —

## 11. What shipped, and where it departs from this text

- 2026-09-28: Steps 0 and 1 on production.
