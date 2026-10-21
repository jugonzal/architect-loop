"""Fail a pull request that carries a runner commit without a `Sponsored-by:` trailer (session-runner D4).

The runner installs a commit-msg hook that adds the trailer, but `git commit --no-verify` skips hooks, so this
check is what enforces it. A runner commit is one whose author or committer is the runner's GitHub App: the bot
login `<slug>[bot]`, or its noreply address `<id>+<slug>[bot]@users.noreply.github.com`. The slug comes from
`--app-slug` or the RUNNER_APP_SLUG environment variable (a repository variable in the trailers workflow). With
no slug set, no commit can be recognised as the runner's, and the check passes and says so.

    python3 trailers.py --base <sha> --head <sha> [--app-slug <slug>] [--repo <path>]

Standard library only: the trailers workflow runs this file as it is on the base branch, with nothing installed.
"""

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass, field

TRAILER = "Sponsored-by"
FIELD = "\x1f"


@dataclass
class Commit:
    sha: str
    author_name: str
    author_email: str
    committer_name: str
    committer_email: str
    message: str

    @property
    def subject(self):
        return self.message.splitlines()[0] if self.message else ""


@dataclass
class Result:
    ok: bool
    runner_commits: int = 0
    failures: list = field(default_factory=list)
    lines: list = field(default_factory=list)


def git(repo, *args, stdin=None):
    result = subprocess.run(["git", "-C", repo, *args], input=stdin, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout


def commits(repo, base, head):
    """Every commit the pull request adds: reachable from head and not from base, merges included."""
    out = git(repo, "log", "-z", f"--format=%H{FIELD}%an{FIELD}%ae{FIELD}%cn{FIELD}%ce{FIELD}%B", f"{base}..{head}")
    found = []
    for record in out.split("\0"):
        if not record.strip():
            continue
        sha, an, ae, cn, ce, message = record.lstrip("\n").split(FIELD, 5)
        found.append(Commit(sha, an, ae, cn, ce, message))
    return found


def is_runner(commit, slug):
    if not slug:
        return False
    login = f"{slug}[bot]"
    suffix = f"+{login}@users.noreply.github.com".lower()
    for name, email in ((commit.author_name, commit.author_email), (commit.committer_name, commit.committer_email)):
        email = email.lower()
        if name == login or email.endswith(suffix) or email == f"{login}@users.noreply.github.com".lower():
            return True
    return False


def trailers(repo, message):
    """The message's trailers as git itself parses them: only the final trailer block counts."""
    out = git(repo, "interpret-trailers", "--parse", "--no-divider", stdin=message)
    parsed = []
    for line in out.splitlines():
        key, sep, value = line.partition(":")
        if sep:
            parsed.append((key.strip(), value.strip()))
    return parsed


def sponsored(repo, commit):
    return any(key.lower() == TRAILER.lower() and value for key, value in trailers(repo, commit.message))


def check(repo, base, head, slug):
    found = commits(repo, base, head)
    if not slug:
        return Result(True, 0, [], [
            f"ok   {len(found)} commits checked; RUNNER_APP_SLUG is not set, so no commit is recognised as the "
            "runner's. Set the repository variable once the runner's GitHub App exists."])
    ours = [c for c in found if is_runner(c, slug)]
    failures = [c for c in ours if not sponsored(repo, c)]
    lines = [f"FAIL {c.sha[:12]} {c.subject!r}: a commit by {slug}[bot] has no {TRAILER}: trailer" for c in failures]
    if failures:
        lines.append(f"     every runner commit names its sponsor (session-runner D4); a commit made with "
                     f"--no-verify skips the hook that adds it")
    else:
        lines.append(f"ok   {len(found)} commits checked, {len(ours)} by {slug}[bot], each with {TRAILER}:")
    return Result(not failures, len(ours), failures, lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--app-slug", default=os.environ.get("RUNNER_APP_SLUG", ""))
    parser.add_argument("--repo", default=".")
    args = parser.parse_args(argv)
    result = check(args.repo, args.base, args.head, args.app_slug.strip())
    for line in result.lines:
        print(line)
    if not args.app_slug.strip():
        print("::warning::RUNNER_APP_SLUG is not set: the trailer check recognises no runner commits")
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
