#!/bin/sh
# The smoke test (LOOP.md §4; command-center/local-harness C2): bring the local harness up at HEAD, as up.sh does,
# then dispatch a /loop-build to the local runner and follow it from start to end against the fake GitHub and the
# fake Agent SDK, check that threads answers a member's read and post, and read every local/<service> row of
# LOOP.md §3 with its own command. It prints one line per check and exits 1 if any fails. Nothing leaves the machine
# and nothing is spent.
#
# It leaves the harness running, so /loop-status can read the local rows; sh scripts/local/down.sh stops it. With
# --no-up it runs the checks against what up.sh already started at HEAD. See docs/runbooks/local.md.
#
# Usage: sh scripts/local/smoke.sh [--no-up]
set -eu

here=$(cd "$(dirname "$0")/../.." && pwd)
exec python3 "$here/scripts/local/harness.py" smoke "$@"
