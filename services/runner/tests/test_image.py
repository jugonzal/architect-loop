"""The runner's image: what a session's job finds installed.

A session runs the skills in its own clone, and the skills run the project's commands. `/loop-status` reads each
environment's served commit with the command in its `LOOP.md` §3 row, which is `sh scripts/gcp/served.sh <url>`
for every service. A program that command needs and the image lacks makes every such row read as unknown inside
a session, so the session sees no concern as shipped or done (app-inbox C2, contradicted on 2026-11-13: the image
installed curl to fetch a key and then purged it).
"""

import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
DOCKERFILE = os.path.join(ROOT, "services", "runner", "Dockerfile")
SERVED = os.path.join(ROOT, "scripts", "gcp", "served.sh")

# Programs served.sh may call that are not part of the base image's shell and coreutils.
FETCHERS = ("curl", "wget")


def packages(dockerfile, verb):
    """The packages every `apt-get <verb>` in the Dockerfile names, flags left out."""
    text = re.sub(r"\\\n", " ", dockerfile)
    found = set()
    for words in re.findall(r"apt-get\s+%s\s+([^&;\n]*)" % verb, text):
        found.update(w for w in words.split() if not w.startswith("-"))
    return found


def kept(dockerfile):
    return packages(dockerfile, "install") - packages(dockerfile, "purge") - packages(dockerfile, "remove")


def commands(script):
    """The words of a shell script that are not in its comments."""
    code = "\n".join(line.split("#", 1)[0] if line.lstrip().startswith("#") else line for line in script.splitlines())
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_-]*", code))


class PackagesTest(unittest.TestCase):
    def test_a_package_installed_and_then_purged_is_not_kept(self):
        dockerfile = ("RUN apt-get update \\\n && apt-get install -y --no-install-recommends git curl gnupg \\\n"
                      " && apt-get install -y gh \\\n && apt-get purge -y curl gnupg \\\n && apt-get autoremove -y\n")
        self.assertEqual(kept(dockerfile), {"git", "gh"})

    def test_a_comment_that_names_a_program_is_not_a_call(self):
        self.assertEqual(commands("# uses wget, once\nbody=$(curl -fsS \"$url\")\n") & set(FETCHERS), {"curl"})


class ImageTest(unittest.TestCase):
    def setUp(self):
        with open(DOCKERFILE) as f:
            self.kept = kept(f.read())

    def test_the_image_keeps_git_and_gh_for_the_skills(self):
        self.assertLessEqual({"git", "gh"}, self.kept)

    def test_the_image_keeps_what_the_served_commit_command_runs(self):
        with open(SERVED) as f:
            needs = commands(f.read()) & set(FETCHERS)
        self.assertTrue(needs, "served.sh no longer calls curl or wget: update what this test looks for")
        self.assertLessEqual(needs, self.kept,
                             "scripts/gcp/served.sh runs %s, which the runner's image does not keep, so a session "
                             "reads every LOOP.md §3 service row as unknown" % ", ".join(sorted(needs - self.kept)))


if __name__ == "__main__":
    unittest.main()
