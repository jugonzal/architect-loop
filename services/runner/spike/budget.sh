#!/bin/sh
# s5a-c: more budget stops. Run after run.sh, with the same SPIKE_DIR and SPIKE_SHA.
#
# In run.sh, two of the three $0.10 runs ended under budget: a denied compound command ended them first.
# A $0.03 budget is crossed within the first few turns, so each run measures the stop and its overshoot.
set -eu

here=$(cd "$(dirname "$0")" && pwd)
env_file=${SPIKE_ENV_FILE:-$HOME/.config/architect-loop/spike.env}
dir=${SPIKE_DIR:?set SPIKE_DIR}
sha=${SPIKE_SHA:?set SPIKE_SHA}
budget=${SPIKE_BUDGET_USD:-0.03}
image=architect-loop-runner-spike:0.2.168

for label in s5a s5b s5c; do
  work="$dir/sessions/$label"
  rm -rf "$work" && git clone -q "$dir/origin.git" "$work" && git -C "$work" checkout -q "$sha"
  git -C "$work" remote set-url origin /origin.git
  docker run --rm --env-file "$env_file" \
    -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0='*' \
    -v "$work:/work" -v "$dir/origin.git:/origin.git:ro" -v "$dir/release/plugin:/plugin:ro" -v "$dir/out:/out" \
    "$image" --label "$label" --budget "$budget" --prompt "/architect-loop:loop-status command-center" \
    --allow Skill Read Glob Grep "Bash(git *)" "Bash(ls *)" "Bash(cat *)" "Bash(head *)" "Bash(sed *)" \
    "Bash(grep *)" "Bash(wc *)" "Bash(date *)" "Bash(find *)"
done
