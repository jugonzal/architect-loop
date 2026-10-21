#!/usr/bin/env python3
"""A fake gh for tests/test_loop_status.py, so gathering facts is tested without a network or an account.

The test puts a `gh` shim first on PATH that runs this file. It answers only the calls loop_status.py and
check_loop_pr.sh make, from the JSON state in $FAKE_GH_STATE, and appends every call to $FAKE_GH_LOG:

    gh pr list --repo R --state all --limit N --json FIELDS
    gh pr view N [--repo R] --json FIELDS [--jq .field]      (R from GH_REPO when --repo is absent)
    gh run list --repo R --commit SHA [--limit N] --json FIELDS
    gh api repos/R --jq .default_branch
    gh api repos/R/compare/A...B --jq .status

The state is {"authenticated": bool, "repositories": {R: {"pull_requests": [...], "runs": {sha: [...]},
"default_branch": "main", "on_main": [sha, ...]}}}. With "authenticated": false every call fails the way gh does
when it has no token. Anything else exits 1, so a call the tests did not expect shows up as a failure.
"""

import json
import os
import sys

NOT_AUTHENTICATED = ("To get started with GitHub CLI, please run:  gh auth login\n"
                     "Alternatively, populate the GH_TOKEN environment variable with a GitHub API authentication token.\n")


def flags(argv):
    out, rest, i = {}, [], 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            key, eq, value = a[2:].partition("=")
            if eq:
                out[key] = value
            elif i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                out[key] = argv[i + 1]
                i += 1
            else:
                out[key] = True
        else:
            rest.append(a)
        i += 1
    return out, rest


def emit(value, jq=None):
    if jq:
        if not jq.startswith(".") or not isinstance(value, dict):
            sys.stderr.write("fake gh: unsupported --jq %s\n" % jq)
            return 1
        value = value.get(jq[1:])
        sys.stdout.write(("" if value is None else str(value)) + "\n")
        return 0
    json.dump(value, sys.stdout)
    sys.stdout.write("\n")
    return 0


def pick(item, fields):
    return {f: item.get(f) for f in fields.split(",")}


def main(argv):
    with open(os.environ["FAKE_GH_STATE"], encoding="utf-8") as f:
        state = json.load(f)
    with open(os.environ["FAKE_GH_LOG"], "a", encoding="utf-8") as f:
        f.write(json.dumps(argv) + "\n")
    if not state.get("authenticated", True):
        sys.stderr.write(NOT_AUTHENTICATED)
        return 4
    opts, rest = flags(argv)
    repos = state.get("repositories", {})

    def repo(name):
        if name not in repos:
            sys.stderr.write("GraphQL: Could not resolve to a Repository with the name '%s'. (repository)\n" % name)
            return None
        return repos[name]

    if rest[:2] == ["pr", "list"]:
        r = repo(opts.get("repo"))
        if r is None:
            return 1
        limit = int(opts.get("limit", 30))
        items = sorted(r.get("pull_requests", []), key=lambda p: -p["number"])[:limit]
        return emit([pick(p, opts["json"]) for p in items])
    if rest[:2] == ["pr", "view"] and len(rest) == 3:
        r = repo(opts.get("repo") or os.environ.get("GH_REPO"))
        if r is None:
            return 1
        found = [p for p in r.get("pull_requests", []) if str(p["number"]) == rest[2]]
        if not found:
            sys.stderr.write("GraphQL: Could not resolve to a PullRequest with the number of %s. (repository.pullRequest)\n"
                             % rest[2])
            return 1
        return emit(pick(found[0], opts["json"]), opts.get("jq"))
    if rest[:2] == ["run", "list"]:
        r = repo(opts.get("repo"))
        if r is None:
            return 1
        runs = r.get("runs", {}).get(opts.get("commit"), [])
        return emit([pick(run, opts["json"]) for run in runs])
    if rest[:1] == ["api"] and len(rest) == 2:
        path = rest[1].split("/")
        if len(path) == 3 and path[0] == "repos":
            r = repo("/".join(path[1:3]))
            if r is None:
                return 1
            return emit({"default_branch": r.get("default_branch", "main")}, opts.get("jq"))
        if len(path) == 5 and path[0] == "repos" and path[3] == "compare" and "..." in path[4]:
            r = repo("/".join(path[1:3]))
            if r is None:
                return 1
            base, head = path[4].split("...", 1)
            if head != r.get("default_branch", "main"):
                sys.stderr.write("fake gh: compare only knows the default branch\n")
                return 1
            on_main = any(sha.startswith(base) for sha in r.get("on_main", []))
            return emit({"status": "ahead" if on_main else "diverged"}, opts.get("jq"))
    sys.stderr.write("fake gh: unexpected call: gh %s\n" % " ".join(argv))
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
