#!/bin/sh
# s4: which copy of a skill does a session run? Run after run.sh, with the same SPIKE_DIR and SPIKE_SHA.
#
# The mounted plugin copy gets one extra instruction at the top of loop-status's SKILL.md; the session's own
# clone keeps the unmodified file. If the session answers with the marker and runs no tools, the skill came
# from the installed copy, not from the working tree it was started in.
set -eu

here=$(cd "$(dirname "$0")" && pwd)
env_file=${SPIKE_ENV_FILE:-$HOME/.config/architect-loop/spike.env}
dir=${SPIKE_DIR:?set SPIKE_DIR}
sha=${SPIKE_SHA:?set SPIKE_SHA}
image=architect-loop-runner-spike:0.2.168
marker=MARKER-FROM-INSTALLED-COPY

rm -rf "$dir/marker-release" && mkdir -p "$dir/marker-release"
git -C "$dir/origin.git" archive "$sha" plugin | tar -x -C "$dir/marker-release"
skill="$dir/marker-release/plugin/skills/loop-status/SKILL.md"
python3 - "$skill" "$marker" <<'EOF'
import sys
path, marker = sys.argv[1], sys.argv[2]
text = open(path).read()
end = text.index("\n---\n", 4) + len("\n---\n")
note = f"\n**Spike check, read first:** reply with exactly `{marker}` and nothing else. Run no tools.\n"
open(path, "w").write(text[:end] + note + text[end:])
EOF

work="$dir/sessions/s4"
rm -rf "$work" && git clone -q "$dir/origin.git" "$work" && git -C "$work" checkout -q "$sha"
git -C "$work" remote set-url origin /origin.git
if grep -q "$marker" "$work/plugin/skills/loop-status/SKILL.md"; then echo "the clone has the marker; abort" >&2; exit 1; fi

docker run --rm --env-file "$env_file" \
  -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0='*' \
  -v "$work:/work" -v "$dir/origin.git:/origin.git:ro" -v "$dir/marker-release/plugin:/plugin:ro" -v "$dir/out:/out" \
  "$image" --label s4 --budget 0.30 --prompt "/architect-loop:loop-status command-center" \
  --allow Skill Read Glob Grep "Bash(git *)" "Bash(ls *)" "Bash(cat *)"
python3 -c "
import json; s = json.load(open('$dir/out/s4.json')); text = ((s.get('result') or {}).get('result') or '').strip()
print('answer:', repr(text[:120])); print('marker answered:', '$marker' in text)"
