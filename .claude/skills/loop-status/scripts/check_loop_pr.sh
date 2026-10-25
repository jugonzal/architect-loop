#!/bin/sh
# check_loop_pr.sh: may an agent merge this branch itself, under the loop-document delegation in
# LOOP.md §2.1? It passes only when:
#
#   1. every file the branch adds, changes, renames or deletes is under docs/loops/
#   2. every evidence line it adds about a claim (C#), a goal (G#) or a ship cites a commit that is
#      already on the base branch (a spike's answer, Q#, may cite a branch; `@?` marks a line that
#      cites nothing and that status does not count)
#   3. no existing evidence line is edited or removed, because evidence is append-only
#      (deleting a whole file is a design decision, not an edit, and is allowed)
#   4. with --pr, the pull request targets the base branch (needs gh)
#
# Usage: check_loop_pr.sh [--base <ref>] [--pr <number>]
#   --base  the main branch as fetched; default origin/main, else main
#   --pr    also check that pull request's base branch with gh
#
# Run `git fetch` first. Exit 0: an agent may merge it once its checks pass. Exit 1: leave it for
# the owner. Exit 2: usage or repository error. Read-only: it never changes the repository.
set -eu

base=""
pr=""
while [ $# -gt 0 ]; do
  case $1 in
    --base) [ $# -ge 2 ] || { echo "usage: $0 [--base <ref>] [--pr <number>]" >&2; exit 2; }
            base=$2; shift 2 ;;
    --pr)   [ $# -ge 2 ] || { echo "usage: $0 [--base <ref>] [--pr <number>]" >&2; exit 2; }
            pr=$2; shift 2 ;;
    *)      echo "usage: $0 [--base <ref>] [--pr <number>]" >&2; exit 2 ;;
  esac
done

git rev-parse --git-dir >/dev/null 2>&1 || { echo "FAIL: not a git repository" >&2; exit 2; }
if [ -z "$base" ]; then
  if git rev-parse -q --verify origin/main >/dev/null; then base=origin/main
  elif git rev-parse -q --verify main >/dev/null; then base=main
  else echo "FAIL: neither origin/main nor main exists; pass --base" >&2; exit 2
  fi
fi
git rev-parse -q --verify "$base^{commit}" >/dev/null || { echo "FAIL: no such base: $base" >&2; exit 2; }

problems=$(mktemp)
lines=$(mktemp)
trap 'rm -f "$problems" "$lines"' EXIT

date_re='[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] · '

# 1. Paths. --no-renames, so moving a file out of docs/loops/ shows up as a deletion there.
changed=$(git diff --no-renames --name-only "$base"...HEAD)
if [ -z "$changed" ]; then
  echo "FAIL: the branch changes nothing against $base"
  exit 1
fi
printf '%s\n' "$changed" | while IFS= read -r f; do
  case $f in
    docs/loops/*) ;;
    *) echo "changes a file outside docs/loops/: $f" >>"$problems" ;;
  esac
done

# 2 and 3. Evidence lines, from a diff with renames paired so a moved file is not "new".
git diff -M -U0 "$base"...HEAD -- docs/loops | awk -v re="^$date_re" '
  /^\+\+\+ / { file = substr($0, 5); sub(/^b\//, "", file); next }
  /^--- /    { next }
  /^\+- /    { body = substr($0, 4); if (body ~ re) print "ADD\t" file "\t" body; next }
  /^-- /     { body = substr($0, 4); if (body ~ re && file != "/dev/null") print "DEL\t" file "\t" body; next }
' >"$lines"

while IFS="$(printf '\t')" read -r kind file body; do
  if [ "$kind" = DEL ]; then
    echo "edits or removes an evidence line in $file (evidence is append-only): $body" >>"$problems"
    continue
  fi
  key=$(printf '%s\n' "$body" | awk -F' · ' '{ print $2 }')
  case $key in Q[0-9]*) continue ;; esac
  case $body in *'@?'*) continue ;; esac
  sha=$(printf '%s\n' "$body" | grep -oE '@[0-9a-f]{7,40}' | head -n 1 | cut -c2-) || true
  if [ -z "$sha" ]; then
    echo "evidence line cites no commit in $file: $body" >>"$problems"
  elif ! git cat-file -e "$sha^{commit}" 2>/dev/null; then
    echo "evidence line cites an unknown commit $sha in $file (git fetch?): $body" >>"$problems"
  elif ! git merge-base --is-ancestor "$sha" "$base"; then
    echo "evidence line cites $sha, which is not on $base, in $file: $body" >>"$problems"
  fi
done <"$lines"

# 4. The pull request's base branch.
if [ -n "$pr" ]; then
  want=${base#origin/}
  if command -v gh >/dev/null 2>&1; then
    got=$(gh pr view "$pr" --json baseRefName --jq .baseRefName 2>/dev/null) || got=""
    if [ -z "$got" ]; then
      echo "could not read PR #$pr's base branch with gh" >>"$problems"
    elif [ "$got" != "$want" ]; then
      echo "PR #$pr targets $got, not $want" >>"$problems"
    fi
  else
    echo "gh is not installed, so PR #$pr's base branch cannot be checked" >>"$problems"
  fi
fi

if [ -s "$problems" ]; then
  sed 's/^/FAIL: /' "$problems"
  echo "Leave this pull request for the owner."
  exit 1
fi

n=$(printf '%s\n' "$changed" | wc -l | tr -d ' ')
added=$(grep -c '^ADD' "$lines" || true)
echo "ok: $n file(s), all under docs/loops/; $added new evidence line(s), each citing a commit on $base or a spike."
echo "An agent may merge this once its checks pass (LOOP.md §2.1)."
