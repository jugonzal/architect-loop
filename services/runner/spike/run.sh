#!/bin/sh
# The session-runner Q1 spike, run from a host with Docker and read access to jugonzal/architect-loop.
#
#   SPIKE_ENV_FILE  a file holding ANTHROPIC_API_KEY=..., passed to each container with --env-file and never
#                   read by this script (default ~/.config/architect-loop/spike.env)
#   SPIKE_DIR       where clones and results go (required)
#   SPIKE_SHA       the commit of main to run against (default: the mirror's main)
#   SPIKE_CAP_USD   stop starting sessions once the summed estimates reach this (default 4.00)
#
# Sessions: s1 runs /loop-status with room to finish, s2 commits one file through a runner-installed hook,
# s3a-c run /loop-status again with a $0.10 budget. Each runs in its own container on its own fresh clone,
# with the plugin mounted read-only from a separate copy of plugin/ at the same commit.
set -eu

here=$(cd "$(dirname "$0")" && pwd)
env_file=${SPIKE_ENV_FILE:-$HOME/.config/architect-loop/spike.env}
dir=${SPIKE_DIR:?set SPIKE_DIR}
cap=${SPIKE_CAP_USD:-4.00}
image=architect-loop-runner-spike:0.2.168

[ -f "$env_file" ] || { echo "no key file at $env_file" >&2; exit 2; }
grep -q '^ANTHROPIC_API_KEY=.' "$env_file" || { echo "$env_file has no ANTHROPIC_API_KEY= line" >&2; exit 2; }

docker build -q -t "$image" "$here" >/dev/null
mkdir -p "$dir"
[ -d "$dir/origin.git" ] || git clone -q --mirror https://github.com/jugonzal/architect-loop.git "$dir/origin.git"
sha=${SPIKE_SHA:-$(git -C "$dir/origin.git" rev-parse main)}
rm -rf "$dir/release" && mkdir -p "$dir/release"
git -C "$dir/origin.git" archive "$sha" plugin | tar -x -C "$dir/release"
echo "main @$sha, plugin from a separate copy at the same commit"

spent() { python3 -c "
import json,glob
print(round(sum((json.load(open(f)).get('result') or {}).get('total_cost_usd') or 0 for f in glob.glob('$dir/out/*.json')),4))"; }

session() { # label budget prompt [allowed tools...]
  label=$1 budget=$2 prompt=$3; shift 3
  now=$(spent)
  if python3 -c "import sys; sys.exit(0 if $now + $budget <= $cap else 1)"; then :; else
    echo "skip $label: \$$now spent, cap \$$cap"; return 0
  fi
  work="$dir/sessions/$label"
  rm -rf "$work" && git clone -q "$dir/origin.git" "$work" && git -C "$work" checkout -q "$sha"
  git -C "$work" remote set-url origin /origin.git
  git -C "$work" config user.name "architect-loop runner (spike)"
  git -C "$work" config user.email "runner@invalid"
  [ "$label" = s2 ] && { git -C "$work" switch -q -c spike/q1-commit; cp "$here/commit-msg" "$work/.git/hooks/commit-msg"; chmod +x "$work/.git/hooks/commit-msg"; }
  mkdir -p "$dir/out"
  docker run --rm --env-file "$env_file" \
    -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0='*' \
    -v "$work:/work" -v "$dir/origin.git:/origin.git:ro" -v "$dir/release/plugin:/plugin:ro" -v "$dir/out:/out" \
    "$image" --label "$label" --budget "$budget" --prompt "$prompt" --allow "$@"
}

read_only() { # label budget: /loop-status with read-only tools
  session "$1" "$2" "/architect-loop:loop-status command-center" Skill Read Glob Grep \
    "Bash(git *)" "Bash(ls *)" "Bash(cat *)" "Bash(head *)" "Bash(sed *)" "Bash(grep *)" "Bash(wc *)" \
    "Bash(date *)" "Bash(find *)"
}
read_only s1 2.00
session s2 0.50 "Create a file named SPIKE.md containing the single line 'session-runner Q1 spike', then commit it with the message 'Record the session-runner spike marker'. Do not push." \
  Write Read "Bash(git add *)" "Bash(git commit *)" "Bash(git status*)" "Bash(git log *)"
for run in a b c; do read_only "s3$run" 0.10; done
echo "summed estimate: \$$(spent)"
git -C "$dir/sessions/s2" log -1 --format='%H%n%B' 2>/dev/null || true
