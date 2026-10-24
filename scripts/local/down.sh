#!/bin/sh
# Stop the local harness: remove every container up.sh, smoke.sh and the fake Cloud Run started (they carry the
# label architect-loop-local=1) and the harness's two networks. The stores go with them; nothing outside this machine
# changes. The images stay, as a build cache. See docs/runbooks/local.md.
#
# Usage: sh scripts/local/down.sh
set -eu

here=$(cd "$(dirname "$0")/../.." && pwd)
exec python3 "$here/scripts/local/harness.py" down "$@"
