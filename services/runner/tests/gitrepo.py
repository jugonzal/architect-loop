"""Throwaway git repositories for the tests: nothing here touches a network or a real remote."""

import os
import shutil
import subprocess
import tempfile

HUMAN = ("Juan", "juan@example.com")
SLUG = "architect-loop-runner"
BOT = (f"{SLUG}[bot]", f"1234+{SLUG}[bot]@users.noreply.github.com")


def clean_env(**extra):
    """An environment for git that ignores the developer's own config and hooks."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    env.update(extra)
    return env


def git(cwd, *args, who=HUMAN, committer=None, check=True):
    committer = committer or who
    env = clean_env(GIT_AUTHOR_NAME=who[0], GIT_AUTHOR_EMAIL=who[1], GIT_COMMITTER_NAME=committer[0],
                    GIT_COMMITTER_EMAIL=committer[1])
    result = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


class Repo:
    """A scratch repository with one commit on main."""

    def __init__(self, testcase):
        self.path = tempfile.mkdtemp(prefix="runner-repo-")
        testcase.addCleanup(shutil.rmtree, self.path, True)
        git(self.path, "init", "-q", "-b", "main")
        self.commit("README.md", "hello\n", "Start the repository")
        self.base = self.head()

    def write(self, rel, text):
        path = os.path.join(self.path, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)

    def commit(self, rel, text, message, who=HUMAN, committer=None, flags=()):
        self.write(rel, text)
        git(self.path, "add", rel, who=who)
        git(self.path, "commit", "-q", *flags, "-m", message, who=who, committer=committer)
        return self.head()

    def head(self):
        return git(self.path, "rev-parse", "HEAD")
