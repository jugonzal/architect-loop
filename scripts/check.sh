#!/bin/sh
# Validate every skill: SKILL.md exists, frontmatter has name and description,
# name matches the directory, description fits the 1024-character limit,
# and every relative link inside the skill resolves.
set -eu

here=$(cd "$(dirname "$0")/.." && pwd)
fail=0

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

  for link in $(grep -oE '\]\((templates|references)/[^)]*\)' "$file" | sed 's/^](//; s/)$//'); do
    [ -f "$dir/$link" ] || { echo "FAIL $name: broken link $link"; bad=1; }
  done

  if [ "$bad" -eq 0 ]; then echo "ok   $name"; else fail=1; fi
done

exit "$fail"
