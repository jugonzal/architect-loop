#!/bin/sh
# Validate every skill: SKILL.md exists, frontmatter has name and description,
# name matches the directory, description fits the 1024-character limit,
# every relative link inside the skill resolves, and every shell script parses.
# Retired skills (generation 1 names) must be stubs, and live skills must not
# send anyone to them. Then run the tests, if Python 3 is available.
set -eu

here=$(cd "$(dirname "$0")/.." && pwd)
fail=0
retired="loop-frame loop-decide loop-promote loop-record loop-reconcile"

is_retired() {
  for r in $retired; do [ "$r" = "$1" ] && return 0; done
  return 1
}

for dir in "$here"/skills/*/; do
  dir=${dir%/}
  name=$(basename "$dir")
  bad=0
  file="$dir/SKILL.md"
  if [ ! -f "$file" ]; then echo "FAIL $name: no SKILL.md"; fail=1; continue; fi

  front=$(awk 'NR==1 && $0!="---" {exit} NR>1 && $0=="---" {exit} NR>1 {print}' "$file")
  fname=$(printf '%s\n' "$front" | sed -n 's/^name: *//p')
  desc=$(printf '%s\n' "$front" | sed -n 's/^description: *//p')

  [ "$fname" = "$name" ] || { echo "FAIL $name: frontmatter name is '$fname'"; bad=1; }
  [ -n "$desc" ]         || { echo "FAIL $name: missing description"; bad=1; }
  [ "${#desc}" -le 1024 ] || { echo "FAIL $name: description is ${#desc} chars (max 1024)"; bad=1; }

  for link in $(grep -oE '\]\((templates|references|scripts)/[^)]*\)' "$file" | sed 's/^](//; s/)$//'); do
    [ -f "$dir/$link" ] || { echo "FAIL $name: broken link $link"; bad=1; }
  done

  for script in "$dir"/scripts/*.sh; do
    [ -f "$script" ] || continue
    sh -n "$script" || { echo "FAIL $name: $(basename "$script") does not parse"; bad=1; }
  done

  if is_retired "$name"; then
    case $desc in
      "Retired in architect-loop"*) ;;
      *) echo "FAIL $name: a retired skill's description must start with 'Retired in architect-loop'"; bad=1 ;;
    esac
    [ "$(find "$dir" -type f | wc -l | tr -d ' ')" = 1 ] || { echo "FAIL $name: a retired skill is a stub, SKILL.md only"; bad=1; }
  elif [ "$name" != loop-init ]; then
    # loop-init's upgrade section is the one live place that names the retired skills.
    for r in $retired; do
      if grep -rq -- "$r" "$dir"; then echo "FAIL $name: refers to retired skill $r"; bad=1; fi
    done
  fi

  if [ "$bad" -eq 0 ]; then echo "ok   $name"; else fail=1; fi
done

if [ -d "$here/tests" ]; then
  if command -v python3 >/dev/null 2>&1; then
    if (cd "$here" && python3 -m unittest discover -s tests -q) >/dev/null 2>&1; then
      echo "ok   tests"
    else
      echo "FAIL tests: run 'python3 -m unittest discover -s tests -v' to see why"; fail=1
    fi
  else
    echo "skip tests: python3 not found"
  fi
fi

exit "$fail"
