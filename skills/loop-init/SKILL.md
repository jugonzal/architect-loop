---
name: loop-init
description: Set up a project for the Architect Loop by interviewing the owner and writing LOOP.md, the contract that says who decides, what agents may do alone, which environments exist, how to test and deploy, and where proposals, runbooks and memory live. Use when adopting the architect loop in a new or existing repo, when the user runs /loop-init or asks to "set up the architect loop", "write a LOOP.md", or "define what agents may do here".
license: MIT
metadata:
  author: architect-loop
  version: "0.1"
---

# loop-init

Write the project's contract, `LOOP.md`, and the folders the other loop skills use.

`LOOP.md` exists so that every agent session, including one that has never seen this project, starts
knowing three things: what it may do alone, what it must stop and ask about, and where the shared
memory lives. Without it, agents guess, and a guessed gate is a gate that does not exist.

## Boundary

This skill writes `LOOP.md` and creates `docs/proposals/`, `docs/runbooks/` and `docs/memory/` (each
with a `.gitkeep`) when missing. It changes no code, config or CI, and does not commit: the owner
reviews the contract first.

## Steps

1. **Check what exists.** If `LOOP.md` is already there, read it and switch to *update mode*: ask
   only about sections that are empty, marked `TODO(owner)`, or contradicted by the repo. Look for
   existing conventions before asking: `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, `docs/`, CI
   workflows, package scripts, `Makefile`, container and deploy config, and the last 50 commit
   subjects (`git log --format=%s -50`). Existing practice wins over this skill's defaults.

2. **Draft from the repo first, then ask.** Fill everything you can infer: test and lint commands,
   environments named in deploy scripts or CI, how each environment reports its deployed version,
   branch naming seen in history, whether changes go through PRs. Then ask the owner only what the
   repo cannot answer, in one batch of at most four questions:
   - Who is the owner (the person who decides and promotes)?
   - Which environments exist, and for each: may agents read it?
   - Beyond the defaults below, what must always stop for a human? Is any action delegated to agents
     on a standing basis (for example "merging to `staging` is fine; CD deploys it")?
   - Do documentation-only changes go through PRs like code, or may the owner push them directly?

3. **Write `LOOP.md`** from [templates/LOOP.md](templates/LOOP.md). Keep every section, and write
   `TODO(owner)` for anything unanswered rather than inventing it. Mark inferred values `(inferred)`
   so the owner can confirm them.

4. **Create the folders** that do not exist yet, each with a `.gitkeep`.

5. **Point other agent entry files at it.** If `CLAUDE.md` or `AGENTS.md` exists, propose (do not
   silently make) a one-line addition: `Read LOOP.md before starting work; it defines gates and conventions.`

6. **Report** in five lines or fewer: what was written, what was inferred, the `TODO(owner)` items,
   and the next step. That is usually `/loop-frame` for the first initiative, or `/loop-reconcile` on
   an existing project whose docs may already be stale.

## Default gates

These are the defaults in the template. The owner may add to them; remove items only on the owner's
explicit say-so.

- **Never done by an agent, even after a yes, unless delegated in §2.1:** merging to the main branch;
  deploying or promoting to any shared environment; migrations against shared data.
- **Done by an agent only after a per-action yes:** money (prices, billing, tax, payment settings);
  identity and access (auth providers, roles, admin grants, OAuth/SSO); secrets; legal and public
  text; DNS, certificates, firewall, cloud IAM; deleting or rewriting production data or expiring user
  content; sending anything to real users.

Other loop skills use this same default list when a project has no `LOOP.md`.

## Existing projects

On a brownfield repo, recommend running `/loop-reconcile` right after this skill. Existing docs almost
always claim things the code or the environment no longer supports, and every later skill trusts them.
