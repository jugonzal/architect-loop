#!/bin/sh
# Run every service in services/ on this machine, built from this clean checkout's HEAD with its manifest's
# settings, against Postgres, the Firestore emulator and the fakes in scripts/local/fakes/ (command-center/
# local-harness, per command-center/D53). It refuses a dirty working tree, replaces whatever an earlier run left,
# and returns once each service's /version answers HEAD at http://localhost:<port>/version, the URL of its
# local/<service> row in LOOP.md §3. Every secret it hands a service is made up, and the services and their jobs sit on
# a Docker network with no route off the machine, so it costs nothing and crosses no gate (LOOP.md §2).
#
# It needs docker, git, openssl and python3. sh scripts/local/down.sh stops it. See docs/runbooks/local.md.
#
# Usage: sh scripts/local/up.sh
set -eu

here=$(cd "$(dirname "$0")/../.." && pwd)
exec python3 "$here/scripts/local/harness.py" up "$@"
