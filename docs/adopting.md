# Adopting the loop

The method needs no special tooling: a repository that holds the context, a clear line between what agents do
alone and what waits for a person, and a way to ask each environment which commit it serves.

## Set up once

- [ ] Install the skills (see the README)
- [ ] Run `loop-init`: it writes `LOOP.md` with gates, environments, commands and conventions
- [ ] Give every environment a command that prints the commit it serves (`LOOP.md` §3). Without it, status
      cannot tell merged from shipped
- [ ] Decide whether agents may merge loop-document PRs themselves (`LOOP.md` §2.1; on by default)
- [ ] On an existing project, run `loop-status audit` next; old docs are almost always partly wrong
- [ ] On a generation 1 project, `loop-init` upgrades it instead; see [upgrading.md](upgrading.md)
- [ ] Make sure CI runs on every PR, and that there is a smoke test proving the whole pipeline on synthetic input
      (if there is none, creating it is a good first loop)
- [ ] Point `CLAUDE.md` / `AGENTS.md` at `LOOP.md`

## Every loop

- [ ] **Plan** it when the idea arrives: `loop-plan` puts it in the backlog with its relations to the loops in flight
- [ ] **Design** it when you start it: answer the questions as numbered, dated decisions, until concerns are ready
- [ ] **Build** every ready concern in parallel: one agent, one worktree, one branch and PR each
- [ ] **Prove** on real data or the real environment; if the proof contradicts the design, that concern goes back to design
- [ ] **Ship** by hand, then verify what the environment actually serves
- [ ] **Status** whenever you are unsure: it says what is true, what needs you, and what agents can start now

## Signs it is working

- A new agent session can pick up any concern from its file alone.
- You never have to ask whether something is done; `/loop-status` answers, and you believe it.
- `git log --format=%s` reads like a changelog, and very few commits are bookkeeping.
- Several concerns are in flight at once, and their PRs rarely conflict.
- Some commits are titled "Correct …". That is the method working, not failing.
- The owner spends their time deciding and shipping, not re-explaining context.

## Signs it is not

- A status line, "done" marker or "in progress" note has crept back into `docs/loops/`.
- PRs that change both code and `docs/loops/`, or that build two concerns at once.
- Concerns whose PRs keep touching paths outside their `touches`. The boundaries are in the wrong place.
- A backlog loop whose relations nobody has looked at since it was planned, now active.
- "Fixed" bugs that come back, with no A/B in the history.
- Agents asking the owner questions the repository already answers, or answering ones only the owner should.
