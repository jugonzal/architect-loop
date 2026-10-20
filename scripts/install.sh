#!/bin/sh
# Copy the loop-* skills into a Claude Code skills directory.
#   ./scripts/install.sh --user                  → ~/.claude/skills
#   ./scripts/install.sh --project <dir>         → <dir>/.claude/skills
#   ./scripts/install.sh --dest <skills-dir>     → any agent's skills directory
set -eu

here=$(cd "$(dirname "$0")/.." && pwd)

case "${1:-}" in
  --user)    dest="$HOME/.claude/skills" ;;
  --project) [ -n "${2:-}" ] || { echo "usage: $0 --project <dir>" >&2; exit 2; }
             dest="$2/.claude/skills" ;;
  --dest)    [ -n "${2:-}" ] || { echo "usage: $0 --dest <skills-dir>" >&2; exit 2; }
             dest="$2" ;;
  *)         echo "usage: $0 --user | --project <dir> | --dest <skills-dir>" >&2; exit 2 ;;
esac

mkdir -p "$dest"
for skill in "$here"/plugin/skills/loop-*; do
  name=$(basename "$skill")
  rm -rf "${dest:?}/$name"
  cp -R "$skill" "$dest/$name"
  echo "installed $name → $dest/$name"
done
