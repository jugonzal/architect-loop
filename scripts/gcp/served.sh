#!/bin/sh
# Print the commit a service serves, read from its unauthenticated GET /version, which answers
# {"commit": "<sha>"} (command-center/D9, D32). This is the served-commit command of each service's row in
# LOOP.md §3. It needs no credentials, so agents may run it against any environment.
#
# With an expected SHA it also verifies a deploy: it exits 1 unless the served commit starts with that SHA.
# When /version cannot be read, or does not answer a commit, it prints nothing on stdout, says why on stderr and
# exits non-zero, so the environment reads as unknown and is never guessed.
#
# Usage: sh scripts/gcp/served.sh <https://.../version> [<expected sha>]
set -eu

if [ $# -lt 1 ] || [ $# -gt 2 ]; then
  echo "usage: sh scripts/gcp/served.sh <https://.../version> [<expected sha>]" >&2
  exit 2
fi
url=$1
want=${2:-}

if ! body=$(curl -fsS --max-time 10 "$url"); then
  echo "served: GET $url failed" >&2
  exit 1
fi
commit=$(printf '%s\n' "$body" | sed -n 's/.*"commit"[[:space:]]*:[[:space:]]*"\([0-9a-f]\{7,40\}\)".*/\1/p' | head -n 1)
if [ -z "$commit" ]; then
  echo "served: GET $url answered no commit: $(printf '%s' "$body" | head -c 200)" >&2
  exit 1
fi
if [ -n "$want" ]; then
  case $commit in
    "$want"*) ;;
    *) echo "served: $url serves $commit, not $want" >&2; exit 1 ;;
  esac
fi
printf '%s\n' "$commit"
