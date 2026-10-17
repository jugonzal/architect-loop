# The method

One architect, many agents, and a repository that remembers everything. Generation 1 ran work as a numbered
list of steps in one living proposal, and every skill wrote its progress into that file. It worked for one
stream of work. With many agents in parallel, the shared file became a bottleneck, and status lines written
by hand drifted from reality until nobody could tell whether a step was done.

Generation 2 treats each piece of work the way a functional program treats a function. The rest of this page
is the seven principles that follow from that, and how the loop runs on them.

## Three owners

| Owner | Holds | Never |
| --- | --- | --- |
| **The architect** (one human) | Intent, priority, decisions, merging code, shipping, and the gates: money, identity, legal, secrets, production data | Types most of the code |
| **Agents** (many, short-lived, in parallel) | Planning drafts, design drafts, building, proving, diagnosing, recording | Merges code, deploys, or decides a gated question |
| **The repository** | Everything both must remember: `LOOP.md`, loops and concerns, runbooks, memory, the commit log | Relies on a chat session to hold state |

The human and the agents rarely hand work to each other directly. They hand it through the repository, which
is why any fresh agent session can pick up any concern.

## Loops and concerns

A **loop** is a goal the system should move toward. It lives in `docs/loops/<loop>/`, and its `README.md` holds
the intent, the goals (`G#`), its relations to other loops, and the decisions its concerns share. Many loops can
be tracked at once; most wait in a backlog until the owner starts one.

A **concern** is one outcome within a loop that can be built, proven and shipped on its own. It is one file, and
its front matter and Done when are its contract:

| Part | Meaning | Programming analogue |
| --- | --- | --- |
| Done when (`C1`, `C2`, …) | Falsifiable claims, each with how and where it is proven | the return value |
| `needs` | Concerns that must be done first, and published decisions it relies on | the arguments |
| `touches` | The paths it may change | its scope |
| `effects` | The gates it crosses: migrations, money, secrets, users | its side effects |
| `ships-to` | The environment where every claim must hold | where it runs |

The rest of the file is the concern's body: its design (where we are, options, the approach), its private
decisions and questions, its evidence, and a Shipped note once it is done.

## Seven principles

Each is a well-known programming idea applied to the loop. Together they come to one rule: **prefer structure
to discipline.** When a failure keeps needing a guardrail, change the shape of the system so the failure cannot
be written down.

1. **A concern is a function.** Named by its outcome, never numbered. Any session can call it by name, and a loop
   is a concern made of concerns, so the same verbs work at every scale. If Done when needs an "and" or more than
   three claims, split it. *(Functions and composition; separation of concerns.)*

2. **Independent by default; dependencies are declared, and point at contracts.** Concerns run in parallel unless
   one names another in `needs`, and order is a fact you state, not an accident of layout. When two concerns must
   agree on an interface, the interface becomes its own small concern that both need. Overlapping `touches` are an
   undeclared dependency, caught at design time, not at merge time. Between loops, coupling stays as loose as
   possible: an observation ("relates") over a dependency on a published decision, and that over a dependency on
   another loop's concern. Nothing tighter is allowed. *(Dataflow; dependency inversion; the structured-design
   coupling scale.)*

3. **Local state, immutable shared values.** Each concern owns its file and its `touches`, and an agent working on
   it writes nowhere else. A concern's own decisions are private. Decisions others rely on are published in the
   loop's README and never edited once relied on: a new decision supersedes them, and everything that needed the
   old one shows as stale. *(Lexical scope; immutability; information hiding.)*

4. **Compute status; record only what cannot be recomputed.** No Status lines anywhere. `/loop-status` derives each
   concern's state from facts every time it runs: branches, pull requests, commits on `main`, the commit each
   environment serves, and evidence. A missed event changes nothing, because each run reads the current state of
   the world. Only what no command can re-observe is written down: the owner's decisions, proofs that cannot be
   cheaply replayed, and lessons. *(Referential transparency; normalisation; level-triggered reconciliation;
   make illegal states unrepresentable.)*

5. **Evidence is a value bound to its inputs.** Every verdict names its claim, commit, environment and rung. When
   code under `touches` changes after the proof, or a decision it needed is superseded, the proof goes stale on its
   own, like a cache entry whose key has changed. *(Memoisation; content addressing; build systems.)*

6. **Effects at the edges.** Design, build and local proof are pure: agents run them freely, in parallel, and their
   output can be thrown away. Merging code, deploying, migrations, money, identity, secrets and messages to users
   are effects. A concern declares its effects up front, so the owner sees every gate before work starts, and the
   ship brief lists them as manual steps. *(Functional core, imperative shell.)*

7. **Failure is local and explicit.** CONTRADICTS sends one concern back to design, and its siblings carry on.
   A contradiction escalates to the loop only when it falsifies something others rely on, and then as a question,
   not a rewrite. UNPROVEN is a value of its own: it names what is missing and who can supply it, and it never
   passes. *(Result types; errors handled at the boundary; supervision.)*

## The verbs

| Verb | Human | Agent | Leaves behind | Skill |
| --- | --- | --- | --- | --- |
| Plan | The intent, and why now | Drafts goals and concerns, compares with every other loop | `docs/loops/<loop>/` in the backlog | `loop-plan` |
| Design | Answers questions, picks options, adds constraints | Reads the code, grills the owner, reshapes concerns | Decisions, complete contracts | `loop-design` |
| Build | Reviews and merges | One worktree, branch and PR per concern | A PR with its proof before the merge | `loop-build` |
| Prove | Supplies reality: devices, data, accounts | Tests, smoke runs, A/Bs, measurements; spikes | Verdicts bound to a commit | `loop-prove`, `loop-diagnose` |
| Ship | Deploys, signs off | The brief before, verification after | `ship` lines in each concern | `loop-ship` |
| Status | Reads the queue, says yes to records | Derives everything from facts | Nothing, until a record | `loop-status` |

`loop-runbook` and `loop-incident` run whenever a procedure is run for real, or reality makes itself felt.

## How status is derived

For each concern, `/loop-status` checks these in order, and the first that matches wins:

| State | When |
| --- | --- |
| parked | the owner parked it, by decision |
| contradicted | a claim's latest verdict is CONTRADICTS, and nothing has been decided since |
| open | a blocking question is unanswered or a decision it needs was superseded; or, before anything is built, its contract is incomplete |
| blocked | nothing is built yet, and something in `needs` is not done |
| ready | nothing is built yet (no branch, PR or commit carries its name), and nothing stands in the way |
| building | its branch or PR exists, and none of its work is on `main` |
| merged | its work is on `main`, and its `ships-to` environment does not serve it yet |
| shipped | `ships-to` serves it, and some claim has no current HOLDS there |
| stale | every claim held, but its `touches` or a decision it needs changed since |
| done | every claim has a current HOLDS on `ships-to` |

A loop with no concerns is **open** (design must cut them). A loop is **backlog** until one of its concerns is designed or built, **active** while it is being worked on, and **done**
when every concern is done and every goal holds. Status also lists what needs the owner, sorted by how much
each item unblocks, and what agents can start now.

## Loop documents only describe `main`

Code pull requests never change `docs/loops/`, and loop-document pull requests change nothing else. Proof from
before a merge goes in the code PR's body, where the reviewer reads it. Evidence lines in a concern always cite
a commit already on `main`, except a spike's answer, which may cite the branch it ran on. So a loop document can
never describe work that is still on a branch, and agents may merge loop-document PRs themselves, under a
standing permission in `LOOP.md` §2.1 that `check_loop_pr.sh` verifies before every merge.

## Why each verb exists

**Plan** exists because big ideas arrive while other work is under way. Writing one down as a loop, with its
relations to the loops in flight, keeps the idea without losing focus, and catches overlaps before anyone builds.

**Design** exists because agents build confidently on whatever premise they are given. Reading the code before
asking, sorting what is verified from what is assumed, and grilling the owner one question at a time is where
wrong premises are caught, and a numbered, dated decision can be cited by a PR weeks later.

**Build** is deliberately narrow: one concern, one worktree, one branch, paths fixed by the contract. The commit
log becomes a changelog and a lab notebook at once.

**Prove** is the verb most teams skip with agents, and the one that pays most. "The tests pass" is the weakest
acceptable rung; the strongest is the real environment with real input, which agents usually reach only after
the owner ships. A proof that contradicts the plan is a success: it sends one concern back to design before more
is built on sand.

**Ship** stays human because it is where irreversibility lives: data, money, users, reputation. Keeping it human
also keeps the human's picture of the system current.

**Status** exists because the next agent starts from zero, and so, often, does the owner. Instead of asking anyone
to keep a record current, it recomputes the record from the facts.

## Parallelism

Design drafts, builds and proofs run in parallel: one agent per concern, each in its own worktree and branch.
They do not collide, because each writes only inside its concern's `touches` (for code) or its concern's file
(for loop documents), and design has already checked that no two concerns built at once share a path. Deciding
and shipping stay serial, because the one human's attention is the constraint, and status batches everything
that needs it into one queue.

## Scale

The loop is fractal. A large concern can become a loop of its own. A one-line fix may skip plan and design, but it
still gets proven, shipped by the owner, and recorded if it taught anyone anything.

## Choosing models

Match the model to the depth of reasoning, not the size of the diff. Fast models are fine for scaffolding and
mechanical edits; the strongest available model earns its cost on design, evaluations with competing options, and
diagnosis where a plausible wrong answer is expensive.
