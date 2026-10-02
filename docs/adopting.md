# Adopting the loop

The method needs no special tooling: a repository that holds the context, and a clear line between
what agents do alone and what waits for a person.

## Set up once

- [ ] Install the skills (see the README)
- [ ] Run `loop-init`: it writes `LOOP.md` with gates, environments, commands and conventions
- [ ] On an existing project, run `loop-reconcile` next; old docs are almost always partly wrong
- [ ] Make sure CI runs on every PR, and that there is a smoke test proving the whole pipeline on synthetic input
      (if there is none, its creation is a good first `loop-frame`)
- [ ] Decide where memory lives: the agent's own, or `docs/memory/`
- [ ] Point `CLAUDE.md` / `AGENTS.md` at `LOOP.md`

## Every piece of work

- [ ] **Frame** anything larger than a day, or with an open question or an irreversible step
- [ ] **Decide**: answer the open questions in the document, as numbered, dated decisions
- [ ] **Build**: one intent per branch and PR, citing the section it implements
- [ ] **Prove** on real data or the real environment; if the proof contradicts the plan, reframe
- [ ] **Promote** by hand, then verify what the environment actually serves
- [ ] **Record**: update the Status line, correct disproved claims, update runbooks and memory

## Signs it is working

- A new agent session can pick up an initiative from its proposal alone.
- `git log --format=%s` reads like a changelog.
- Some commits are titled "Correct …". That is the method working, not failing.
- Proposals have more "what shipped and where it departs" text over time, not less.
- The owner spends their time deciding and promoting, not re-explaining context.

## Signs it is not

- Status lines older than the last deploy to the area they describe.
- PRs that do three things.
- "Fixed" bugs that come back, with no A/B in the history.
- Runbooks nobody has run since they were written.
- Agents asking the owner questions the repository already answers, or answering ones only the owner should.
