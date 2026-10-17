## What this changes

<One paragraph in behaviour terms: what a user, operator or downstream system sees differently.>

Builds `<loop>/<concern>` ([`docs/loops/<loop>/<concern>.md`](docs/loops/<loop>/<concern>.md)), claims
C<n>, C<m>. Relies on: <its needs, e.g. `job-contract`, `<loop>/D2`>.

## Why this way

<The reasoning in 2–4 sentences: the alternatives considered and why this one, citing the concern's decisions.>

## How it was proven before the merge

- [ ] Unit tests: `<command>`, <result>
- [ ] Reproducer / regression test: <name>, fails before, passes after
- [ ] Smoke test: `<command>`, <result>
- [ ] C<n>: HOLDS | CONTRADICTS | UNPROVEN (rung <r>, <where>, @<sha>): <one line of evidence>

## Still to prove after the merge

- C<n> on <environment>: <how>. `/loop-prove` records it in the concern once that environment serves this.

## Effects and rollback

<The concern's declared effects that this PR carries, and exactly what the owner must do for each: migrations to
run, secrets to set, settings to change ("None" if none). What could go wrong once deployed; how to roll back;
what does not roll back.>

Concern: <loop>/<concern>
