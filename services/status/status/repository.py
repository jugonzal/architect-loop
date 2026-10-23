"""The service's own clone of a project's repository: where it reads git facts, the way loop-status's gather does.

It is a bare repository under STATUS_CACHE_DIR, at `<owner>/<repo>.git`, whose `refs/remotes/origin/*` mirror the
project's branches. It is a cache: deleting it costs one clone (C3). It holds no token: the installation token
reaches git through the environment of the one command that fetches, never through its config.

Every command here is git, with fixed arguments, plus loop-status's check_loop_pr.sh from the service's own image.
Nothing taken from the repository is ever run (command-center/D9).
"""

import base64
import os
import re
import shutil
import subprocess
import tempfile

from .errors import Unavailable

NUL = "\0"


def _last_line(text, code):
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return lines[-1] if lines else "exit %d" % code


class Clone:
    def __init__(self, project, origin_url, path, log=None):
        self.project = project
        self.origin_url = origin_url
        self.path = path
        self.log = log if log is not None else []
        self.env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.path.dirname(path),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
        }

    def auth_env(self, token):
        """The environment that lets one git command authenticate as the app, for an https origin."""
        if not token or not self.origin_url.startswith("https://"):
            return dict(self.env)
        basic = base64.b64encode(("x-access-token:%s" % token).encode()).decode()
        return dict(self.env, GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.extraHeader",
                    GIT_CONFIG_VALUE_0="Authorization: Basic %s" % basic)

    def git(self, args, env=None, cwd=None, data=None, binary=False, timeout=120):
        argv = ["git", *args]
        try:
            result = subprocess.run(argv, cwd=cwd or self.path, env=env or self.env, input=data,
                                    capture_output=True, timeout=timeout)
            code, out, err = result.returncode, result.stdout, result.stderr.decode("utf-8", "replace")
        except FileNotFoundError as error:
            code, out, err = 127, b"", str(error)
        except subprocess.TimeoutExpired:
            code, out, err = 124, b"", "timed out after %d s" % timeout
        self.log.append({"command": " ".join(argv), "exit": code})
        return code, (out if binary else out.decode("utf-8", "replace")), err

    # Fetching.

    def fetch(self, token):
        """Bring the clone up to date with origin, creating it if needed. Returns origin's default branch."""
        if not os.path.exists(os.path.join(self.path, "HEAD")):
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            shutil.rmtree(self.path, ignore_errors=True)
            code, _, err = self.git(["init", "--quiet", "--bare", self.path], cwd=os.path.dirname(self.path))
            if code:
                raise Unavailable("git init of the cache failed: %s" % _last_line(err, code))
        env = self.auth_env(token)
        code, out, err = self.git(["ls-remote", "--symref", self.origin_url, "HEAD"], env=env, timeout=60)
        if code:
            raise Unavailable("git cannot read %s: %s" % (self.project, _last_line(err, code)))
        match = re.search(r"^ref: refs/heads/(\S+)\tHEAD$", out, re.MULTILINE)
        branch = match.group(1) if match else "main"
        code, _, err = self.git(["fetch", "--quiet", "--prune", "--no-tags", self.origin_url,
                                 "+refs/heads/*:refs/remotes/origin/*"], env=env, timeout=300)
        if code:
            raise Unavailable("git fetch of %s failed: %s" % (self.project, _last_line(err, code)))
        return branch

    def head(self, branch):
        code, out, err = self.git(["rev-parse", "--verify", "--quiet", "refs/remotes/origin/%s^{commit}" % branch])
        if code or not out.strip():
            raise Unavailable("%s has no %s branch to read" % (self.project, branch))
        return out.strip()

    # The facts loop-status's gather reads from git, read the same way.

    def files(self, sha):
        """{path: text} for LOOP.md and every docs/loops/<loop>/<file>.md at sha."""
        code, out, err = self.git(["ls-tree", "-r", "-z", "--name-only", sha, "--", "LOOP.md", "docs/loops"])
        if code:
            raise Unavailable("git ls-tree failed: %s" % _last_line(err, code))
        paths = [p for p in out.split(NUL) if p == "LOOP.md" or re.match(r"^docs/loops/[^/]+/[^/]+\.md$", p)]
        files = {}
        if not paths:
            return files
        code, blob, err = self.git(["cat-file", "--batch"], binary=True,
                                   data="".join("%s:%s\n" % (sha, p) for p in paths).encode())
        if code:
            raise Unavailable("git cat-file failed: %s" % _last_line(err, code))
        at = 0
        for p in paths:
            end = blob.index(b"\n", at)
            header = blob[at:end].decode().split()
            at = end + 1
            if len(header) == 3 and header[1] == "blob":
                size = int(header[2])
                files[p] = blob[at:at + size].decode("utf-8", "replace")
                at += size + 1
        return files

    def branches(self):
        code, out, err = self.git(["for-each-ref", "--format=%(refname:strip=3)%09%(objectname)", "refs/remotes/origin"])
        if code:
            return {"heads": None, "error": _last_line(err, code)}
        heads = dict(line.split("\t", 1) for line in out.splitlines() if "\t" in line)
        heads.pop("HEAD", None)
        return {"heads": heads, "error": None}

    def trailers(self, sha):
        code, out, err = self.git(["log", sha, "--format=%H%x09%(trailers:key=Concern,valueonly,separator=%x2C)"])
        commits = []
        for line in out.splitlines():
            commit, _, refs = line.partition("\t")
            refs = [r.strip() for r in refs.split(",") if r.strip()]
            if refs:
                commits.append({"sha": commit, "concerns": refs})
        return {"commits": commits, "error": None if code == 0 else _last_line(err, code)}

    def merges(self, sha, ls):
        code, out, err = self.git(["log", "--first-parent", sha, "--format=%H%x09%s"])
        commits = []
        for line in out.splitlines():
            commit, _, subject = line.partition("\t")
            if ls.MERGE_SUBJECT_RE.match(subject) or ls.SQUASH_SUBJECT_RE.search(subject):
                commits.append({"sha": commit, "subject": subject})
        return {"commits": commits, "error": None if code == 0 else _last_line(err, code)}

    # A loop-document pull request, checked as loop-status's gather checks one.

    def check_loop_pr(self, pr, main_sha, branch, token, checker):
        """check_loop_pr.sh on the pull request's head, in a throwaway clone that shares this one's objects.

        The terminal also passes --pr, which asks gh for the pull request's base branch; the service already has
        it from GitHub's API and checks only pull requests whose base is main, so it leaves it out.
        """
        out = {"repository": pr["repository"], "number": pr["number"], "head": None, "ok": None, "failures": [],
               "error": None}
        tmp = tempfile.mkdtemp(prefix="status-check-")
        clone = os.path.join(tmp, "repo")
        try:
            steps = [
                (["clone", "--quiet", "--shared", "--no-checkout", self.path, clone], tmp, self.env),
                (["fetch", "--quiet", "--no-tags", self.origin_url, "refs/pull/%d/head" % pr["number"]], clone,
                 self.auth_env(token)),
                (["checkout", "--quiet", "--detach", "FETCH_HEAD"], clone, self.env),
                (["update-ref", "refs/remotes/origin/%s" % branch, main_sha], clone, self.env),
            ]
            for args, cwd, env in steps:
                code, _, err = self.git(args, env=env, cwd=cwd)
                if code:
                    out["error"] = "git %s: %s" % (args[0], _last_line(err, code))
                    return out
            code, head, _ = self.git(["rev-parse", "HEAD"], cwd=clone)
            out["head"] = head.strip() or None
            argv = ["sh", checker, "--base", "origin/%s" % branch]
            try:
                result = subprocess.run(argv, cwd=clone, env=self.env, capture_output=True, timeout=120)
                code, text = result.returncode, result.stdout.decode("utf-8", "replace")
                err = result.stderr.decode("utf-8", "replace")
            except subprocess.TimeoutExpired:
                code, text, err = 124, "", "timed out"
            self.log.append({"command": "sh check_loop_pr.sh --base origin/%s" % branch, "exit": code})
            if code == 0:
                out["ok"] = True
            elif code == 1:
                out["ok"] = False
                out["failures"] = [line.strip() for line in text.splitlines() if line.startswith("FAIL")]
            else:
                out["error"] = "check_loop_pr.sh exited %d: %s" % (code, _last_line(err or text, code))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        return out
