# Runbook: run every service on one machine against fakes, and the smoke test

**Status:** run end to end, on a branch | **Last run as written:** 2026-10-24 on a developer's Mac (Docker
Desktop, Apple silicon), by an agent building `command-center/local-harness`, from commits of its branch, not yet
on `main`: steps 1 to 3 three times, and step 4 once. Every expected output below is what those runs printed,
with the commit written `<sha>`. CI's first run, in `.github/workflows/local.yml` on Ubuntu, is not recorded here
yet.

Use this to run the command center's services on one machine, from a clean checkout of a commit, so a claim can be
proven before staging (command-center/D53), and to run `LOOP.md` §4's smoke test. Afterwards every service in
`services/` runs in Docker at that commit, with its manifest's settings, against Postgres, the Firestore emulator
and the fakes in `scripts/local/fakes/` (GitHub, the Agent SDK, Cloud Run's job launch and the metadata server), and
each one's `/version` answers the commit at the URL its `local/<service>` row in `LOOP.md` §3 reads. It costs
nothing and crosses no gate: every secret it hands a service is made up, and the services, their jobs and the
stores sit on a Docker network with no route off the machine. It proves the wiring, not GitHub or the SDK.

## Quick reference

```bash
git status --short --untracked-files=no      # nothing: a dirty tree is refused
sh scripts/local/smoke.sh                     # up at HEAD, one session end to end, threads, the local rows
sh scripts/gcp/served.sh http://localhost:8702/version "$(git rev-parse HEAD)"   # any local row, by hand
sh scripts/local/down.sh                      # stop it all
```

`sh scripts/local/up.sh` starts the harness without the checks, and `sh scripts/local/smoke.sh --no-up` runs the
checks against what it started.

## Preconditions

- Docker running (Docker Desktop on a Mac, or the Docker Engine on Linux), with the socket at
  `/var/run/docker.sock`: the fake Cloud Run starts each session's job through it. About 2.5 GB of disk for the
  images, most of it the runner's (the Agent SDK's wheel bundles Claude Code) and the Firestore emulator's.
- `git`, `openssl`, `curl`, `sh` and `python3` (3.9 or later, standard library only).
- A clean checkout of the commit to run: no tracked file may differ from HEAD (untracked files are left alone; they
  cannot reach an image). For an evidence line, the commit must be on `origin/main`: an evidence line cites
  `local @<sha>` only for a commit on `main` (LOOP.md §6). `up` says whether it is.
- The release tags fetched (`git fetch --tags`): a session installs the plugin from the latest release tag
  reachable from HEAD. In CI, check out with `fetch-depth: 0`.
- Free ports on 127.0.0.1: 8701 to 8704 (the services, in `SERVICES` order in `scripts/gcp/common.sh`), 8711 to 8713
  (the fakes) and 8721 (the Firestore emulator).
- No credentials of any kind. Nothing here signs in to GitHub, Google or Anthropic.
- Expected cost: nothing. Building the images downloads their packages and base images, as any build does.

## Steps

### 1. Bring it up

```bash
sh scripts/local/up.sh
```

It builds `scripts/local/fakes/Dockerfile` and every `services/<name>/Dockerfile` from HEAD's own tree, as
`deploy.sh` does, tagged `architect-loop-local/<name>:<sha>`; makes the fake GitHub's copy of the repository
(HEAD as `main`, and every tag); starts Postgres, the emulator and the fakes; creates and migrates the database of
each service whose manifest names `cloudsql`; starts each service; and waits for each `/version`. It removes what
an earlier run left first, so the stores start empty. Expected, on a commit not yet on `main`:

```
up: local at <sha>, which is NOT on origin/main: an evidence line cannot cite this run
ok   built architect-loop-local/fakes:<sha>
ok   built architect-loop-local/status:<sha>
ok   built architect-loop-local/runner:<sha>
ok   built architect-loop-local/threads:<sha>
ok   fakes: GitHub on 8711, Cloud Run on 8712, the metadata server on 8713
ok   Postgres, and the Firestore emulator on 8721
ok   the threads database: applied 0001_threads.sql
ok   local/status answers <sha> at http://localhost:8701/version
ok   local/runner answers <sha> at http://localhost:8702/version
ok   local/threads answers <sha> at http://localhost:8703/version
up: 3 services at <sha>; sh scripts/local/smoke.sh --no-up runs the smoke test against them, and sh scripts/local/down.sh stops them
```

On a commit on `origin/main`, the first line ends `, a commit on origin/main`. The first build takes minutes, most
of them downloading the runner's packages (see Traps). With Docker's cache, `sh scripts/local/smoke.sh`, from the
first build line to its last check, took 21 s.

**Failure signatures:**

- `up: the working tree is dirty, so it is not the commit /version would answer; commit or stash:` and the changed
  paths: commit or stash them. Nothing was stopped or started.
- `note building architect-loop-local/<name>:<sha> failed (attempt 1 of 3); trying again`: usually a package
  download that timed out (see Traps). After three failures it prints the end of the build log and stops.
- `FAIL local/<name>: http://localhost:<port>/version answering <sha> did not happen within 90 s` and the
  service's last log lines: the service did not start with its local config. `python3 scripts/local/harness.py env
  <name>` prints the environment it was given, keys elided.
- `docker ... failed (125): ... port is already allocated`: something else holds one of the ports above.

### 2. Read the local rows

```bash
sh scripts/gcp/served.sh http://localhost:8701/version
python3 scripts/local/harness.py rows
```

Each row of a service in `services/` prints HEAD's SHA. `local/notify` reads as unknown until `services/notify/`
exists, which is true:

```
ok   LOOP.md §3 has local rows
ok   local/status reads <sha7> with `sh scripts/gcp/served.sh http://localhost:8701/version`
ok   local/runner reads <sha7> with `sh scripts/gcp/served.sh http://localhost:8702/version`
ok   local/threads reads <sha7> with `sh scripts/gcp/served.sh http://localhost:8703/version`
note local/notify reads as unknown: services/notify is not built yet (curl: (7) Failed to connect to localhost port 8704 after 0 ms: Couldn't connect to server
served: GET http://localhost:8704/version failed)
```

`/loop-status`, from an installed release, reads the same rows from `LOOP.md` on `main`, so it shows them once
they are on `main` and the harness is up on the machine it runs on (command-center/local-harness C1).

### 3. Run the smoke test

```bash
sh scripts/local/smoke.sh --no-up      # or without --no-up, which runs step 1 first
```

It dispatches a `/loop-build` as the made-up collaborator `local-sponsor` on the first concern on HEAD (or the one
`LOCAL_SMOKE_CONCERN` names), with the latest release tag, and follows the session to its end. The job runs the
fake Agent SDK, which commits one file, pushes the concern's branch to the fake GitHub and opens a pull request
there. Then it checks threads as the member `local-member` and the outsider `local-outsider`, and reads the local
rows as in step 2. Expected:

```
smoke: /loop-build on command-center/addressed-to-people, plugin v0.4.0, sponsored by local-sponsor, at local @<sha>
ok   the runner accepts a dispatch from a collaborator
ok   a second /loop-build on the concern is refused while the first holds it
ok   the runner refuses a dispatch from someone who does not collaborate
ok   the concern is claimed in the runner's Firestore database, which its jobs share
ok   spend is published while the session runs
ok   the session runs from start to end
ok   its final spend is published, as the (fake) SDK's estimate
ok   its final message is kept
ok   the session's job ran in its own container, apart from the runner's, and exited 0
ok   the session opened a pull request on the fake GitHub, and the session lists it
ok   its pull request body carries Concern: and Sponsored-by:
ok   its commit carries Concern: and Sponsored-by: from the runner's hook
ok   the runner asked the fakes, not GitHub or Google: who calls, a collaborator check, installation tokens, the concern, the release, a push and a job execution
ok   every service, job and store is on architect-loop-local-internal only, a network with no route off the machine
ok   a container on architect-loop-local-internal reaches neither api.github.com nor 1.1.1.1
ok   threads answers a member's read of the concern's thread
ok   threads takes a member's post
ok   the member reads their post back
ok   threads refuses someone who is not a member
ok   a review on the session's pull request reaches the concern's thread, by the fake GitHub's webhook
ok   threads takes a post to the session's thread with the runner's ID token, checked against the fake metadata server's keys
ok   a member reads it
ok   LOOP.md §3 has local rows
ok   local/status reads <sha7> with `sh scripts/gcp/served.sh http://localhost:8701/version`
ok   local/runner reads <sha7> with `sh scripts/gcp/served.sh http://localhost:8702/version`
ok   local/threads reads <sha7> with `sh scripts/gcp/served.sh http://localhost:8703/version`
note local/notify reads as unknown: ...
smoke: all 26 checks hold at local @<sha>; sh scripts/local/down.sh stops the harness
```

It exits 0 only when every check holds; a failing check prints `FAIL <check>: <what it saw>`. The session took about
ten seconds from dispatch to its end, eight of them the fake SDK's own.

To look further while it is up: `curl -s -H 'Authorization: Bearer local-sponsor-token'
http://localhost:8702/sessions?state=all` lists the sessions, `curl -s http://localhost:8711/_local/calls` lists
every call the fakes answered and the fake pull requests, `docker ps -a --filter label=architect-loop-local=1`
lists the containers (each session's job is `architect-loop-local-runner-session-<suffix>`), and `docker logs
<container>` shows what one said.

### 4. Stop it

```bash
sh scripts/local/down.sh
```

Expected: `down: removed <n> containers and the networks architect-loop-local and architect-loop-local-internal`.
The stores go with the containers. The images stay as Docker's cache; `docker image rm $(docker images -q
'architect-loop-local/*')` removes them.

## Verify

`sh scripts/local/smoke.sh` ends `smoke: all <n> checks hold at local @<sha>` with exit status 0, and
`sh scripts/gcp/served.sh http://localhost:<port>/version <sha>` prints the SHA for each service. In CI,
`.github/workflows/local.yml` runs the harness's own tests and then the smoke test on every push and pull request.

## Rollback

Nothing outside the machine changes, so there is nothing to roll back: `sh scripts/local/down.sh` removes
everything the harness started. To undo the harness itself, revert its pull request; staging is unchanged, since
every setting it added to the runner and threads defaults to what they did before.

## Traps

Each learned in a real run. Newest first.

- **2026-10-24:** the first `up` failed twice building the runner, then threads, with
  `ReadTimeoutError: HTTPSConnectionPool(host='files.pythonhosted.org', port=443): Read timed out.` in
  `pip install`. It was downloading the Agent SDK's 114 MB wheel from inside Docker; the same build, run again by
  hand, passed. `up` now tries each build up to three times, and prints `note building ... trying again`.
- **2026-10-24:** a bare repository made by `git init --bare` points HEAD at `master` on a machine whose git
  defaults to it, so a clone from the fake GitHub checked out nothing. The harness makes it with
  `--initial-branch=main`.

## Corrections

None yet.
