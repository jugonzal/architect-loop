"""The facts document, gathered by the service itself (status-derivation C3, command-center/D9, D15).

It has exactly the shape `loop_status.py gather` writes, so `derive` reads the service's facts and the terminal's
alike. What differs is how each fact is read:

| Fact | The terminal (`gather`) | The service |
| --- | --- | --- |
| main, files, branches, trailers, merges | git on the working repository | git on its own clone, the same commands |
| environments | each row's served-commit command | a GET of the row's first http(s) URL (served.py) |
| pull requests | `gh pr list` / `gh pr view` | GitHub's GraphQL API, in gh's shape (github.py) |
| checks on main | `gh run list --commit` | GitHub's workflow runs API |
| other repositories | `gh api` | GitHub's REST API, with the same app |
| loop-document checks | check_loop_pr.sh on each open one | the same script, from the service's image |
| git questions | git, and `gh api .../compare` | git on its clone, and the compare API |

A fact that cannot be read keeps its error, so what rests on it derives as unknown. Main is the exception: without
it there is nothing to derive, so a failure to fetch raises Unavailable and the caller answers 503.
"""

import os
from datetime import datetime, timezone

from .errors import Unavailable
from .repository import Clone
from . import derivation, served

ROUNDS = 8  # as many rounds of git questions as gather answers


def utcnow():
    return datetime.now(timezone.utc)


class Gatherer:
    def __init__(self, project, *, settings, github, ls, now=utcnow, checker=derivation.CHECKER):
        self.project = project
        self.settings = settings
        self.github = github
        self.ls = ls
        self.now = now
        self.checker = checker
        self.origin_url = "%s/%s.git" % (settings.github_git_url.rstrip("/"), project)
        self.path = os.path.join(settings.cache_dir, project + ".git")

    def facts(self):
        ls = self.ls
        log = []
        clone = Clone(self.project, self.origin_url, self.path, log)
        as_of = self.now().astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        token = self.github.installation_token(self.project)
        branch = clone.fetch(token)
        sha = clone.head(branch)
        facts = {"facts_version": ls.FACTS_VERSION, "project": self.project, "as_of": as_of,
                 "main": {"branch": branch, "sha": sha, "error": None}}
        files = clone.files(sha)
        facts["files"] = files

        facts["environments"] = served.environments(ls, files.get("LOOP.md"), sha,
                                                    self.settings.served_timeout_seconds)
        log.append({"command": "GET each LOOP.md §3 row's served-commit URL", "exit": 0})

        try:
            runs = self.github.workflow_runs(self.project, sha)
            facts["ci"] = {"commit": sha, "state": ls.runs_state(runs), "error": None}
        except Unavailable as error:
            facts["ci"] = {"commit": sha, "state": "unknown", "error": str(error)}

        # Pull requests, in the project and in every other repository a touches or prs entry names.
        model = ls.Project(dict(facts, branches={"heads": {}, "error": None}, trailers={"commits": [], "error": None},
                                pull_requests=[], answers=[]))
        wanted = {}
        for c in model.concerns():
            for repo, number in c.pr_refs:
                wanted.setdefault(repo, set()).add(number)
        facts["pull_requests"], facts["repositories"] = [], []
        for repo in [self.project] + model.other_repositories():
            entry = {"repository": repo, "items": [], "error": None}
            try:
                entry["items"] = [ls.normalize_pr(raw, repo) for raw in self.github.pull_requests(repo)]
                for number in sorted(wanted.get(repo, set()) - {p["number"] for p in entry["items"]}):
                    raw = self.github.pull_request(repo, number)
                    if raw is not None:
                        entry["items"].append(ls.normalize_pr(raw, repo))
            except Unavailable as error:
                entry = {"repository": repo, "items": [], "error": str(error)}
            facts["pull_requests"].append(entry)
            if repo != self.project:
                try:
                    facts["repositories"].append({"repository": repo, "default_branch":
                                                  self.github.default_branch(repo), "error": None})
                except Unavailable as error:
                    facts["repositories"].append({"repository": repo, "default_branch": None, "error": str(error)})

        facts["branches"] = clone.branches()
        facts["trailers"] = clone.trailers(sha)
        facts["merges"] = clone.merges(sha, ls)

        # check_loop_pr.sh on each open loop-document pull request, as gather picks them.
        facts["loop_document_checks"] = []
        loop_ids = sorted({p.split("/")[2] for p in files if p.startswith("docs/loops/")}, key=len, reverse=True)
        project_prs = next((e for e in facts["pull_requests"] if e["repository"] == self.project), {})
        for pr in project_prs.get("items") or []:
            if pr["state"] != "open" or pr["draft"] or pr["base"] != branch:
                continue
            if not any(pr["head"].startswith("docs/%s-" % loop_id) for loop_id in loop_ids):
                continue
            facts["loop_document_checks"].append(clone.check_loop_pr(pr, sha, branch, token, self.checker))

        # The git questions the derivation asks, answered until none is left.
        facts["answers"] = []
        runner = ls.Runner(self.path, clone.env)
        for _ in range(ROUNDS):
            pending = ls.pending_queries(facts)
            if not pending:
                break
            for query in pending:
                facts["answers"].append(self.answer(runner, query))
        log += runner.log
        facts["log"] = log
        return facts

    def answer(self, runner, query):
        """One git question: with git on the clone for the project, with GitHub's compare API for another one."""
        if query["repository"] == self.project:
            return self.ls.answer(runner, query, self.project)
        out = {"query": query, "value": None, "error": None}
        if query["kind"] != "ancestor":
            out["error"] = "%s questions about %s cannot be answered from this repository" % (
                query["kind"], query["repository"])
            return out
        try:
            status = self.github.compare_status(query["repository"], query["commit"], query["of"])
        except Unavailable as error:
            out["error"] = str(error)
            return out
        if status in ("ahead", "identical", "behind", "diverged"):
            out["value"] = status in ("ahead", "identical")
        else:
            out["error"] = "GitHub compared them as %r" % status
        return out
