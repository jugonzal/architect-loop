# Runbook: <topic>

**Status:** draft — not yet run | **Last run as written:** YYYY-MM-DD on <environment> by <who>

<One sentence: when to use this runbook, and what state the system is in afterwards.>

## Quick reference

```bash
<the three to six commands someone who has done this before needs>
```

## Preconditions

- <access, tools, versions, state the system must be in>
- <who must be available: the owner for gated steps>

## Steps

### 1. <step name>

```bash
<exact command>
```

- **Success prints:** `<expected output or pattern>`
- **Failure looks like:** <symptom, and what it usually means>
- **Safe to re-run:** yes | no, because <reason>

### 2. …

## Verify

```bash
<commands>
```

<What each should print when the procedure succeeded.>

## Rollback

<Exact steps. Then: what does not roll back (data, sent messages, external state).>

## Traps

Each learned in a real run. Newest first.

- **YYYY-MM-DD:** <what happened> → <why> → <how to avoid it>

## Corrections

- YYYY-MM-DD: <which steps changed after which run, in one line>
