"""Tests for plugin/skills/loop-status/scripts/loop_status.py, the loop-status derivation as one script.

command-center/status-derivation:
- C1: given the same facts, the script derives the state the derivation table in loop-status's SKILL.md gives, for
  every concern and loop, including unknown. TableTest has one case per row of the table and per definition under
  it (serves, current HOLDS, `@?`, unknown, a pull request merged in another repository per command-center/D19,
  and a claim that holds by CI on main at rung 5). WorldTest derives a whole fixture world (tests/fixtures/
  loop_status/) holding every row at once, and checks it against expected.json, worked out by hand from the table.
  SkillTest checks that the script's states are exactly the table's, so the two cannot drift apart.
- C2: every document derived here, in every test, validates against status.schema.json (with the small validator
  of tests/test_status_schema.py), and every concern carries its reason and the facts it came from.
- C3: gathering is separate from deriving. WorldTest builds the world twice: as a real git repository with a bare
  origin and a fake gh, which loop_status.py gathers from, and as a facts document supplied directly, the way the
  status service supplies one, whose git questions an independent commit graph answers. Both give the same
  document, and so do the command line's default, `gather` then `derive --facts`, and stdin.

Nothing here touches a network or a real account: git runs on temporary repositories, gh is
tests/fixtures/loop_status/fake_gh.py placed first on PATH, and the served-commit commands read local files.

Run from the repository root: python3 -m unittest discover -s tests -v
"""

import copy
import fnmatch
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from test_status_schema import Validator, derivation_table_states, loop_states_in_step_5, recommendation_problems  # noqa: E402

ROOT = os.path.dirname(HERE)
SKILL_DIR = os.path.join(ROOT, "plugin", "skills", "loop-status")
SCRIPT = os.path.join(SKILL_DIR, "scripts", "loop_status.py")
SCHEMA = os.path.join(SKILL_DIR, "scripts", "status.schema.json")
SKILL = os.path.join(SKILL_DIR, "SKILL.md")
FIXTURES = os.path.join(HERE, "fixtures", "loop_status")
FAKE_GH = os.path.join(FIXTURES, "fake_gh.py")

_spec = importlib.util.spec_from_file_location("loop_status", SCRIPT)
ls = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ls)

with open(SCHEMA, encoding="utf-8") as _f:
    VALIDATOR = Validator(json.load(_f))

PROJECT = "example/reports"
AS_OF = "2026-10-21T09:00:00Z"


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def check_document(test, doc):
    """C2, for every document any test derives: it validates, and each concern says why and from what."""
    test.assertEqual(VALIDATOR.errors(doc), [], "the derived document does not validate")
    test.assertEqual(recommendation_problems(doc), [])
    for loop in doc["loops"]:
        test.assertTrue(loop["reason"], loop["id"])
        if loop["state"] == "unknown":
            test.assertIn("cannot be read", loop["reason"] + " " + str(loop["next"]), loop["id"])
        for concern in loop["concerns"]:
            inputs = concern["inputs"]
            test.assertTrue(concern["reason"], concern["id"])
            test.assertEqual(inputs["main"], doc["main"]["sha"], concern["id"])
            test.assertEqual(inputs["served"]["environment"], concern["contract"]["ships_to"], concern["id"])
            if concern["state"] == "unknown":
                test.assertTrue(inputs.get("missing"), "%s is unknown but names no missing fact" % concern["id"])


def states(doc):
    return {"%s/%s" % (loop["id"], c["id"]): c["state"] for loop in doc["loops"] for c in loop["concerns"]}


def concern(doc, ref):
    loop_id, concern_id = ref.split("/")
    loop = next(l for l in doc["loops"] if l["id"] == loop_id)
    return next(c for c in loop["concerns"] if c["id"] == concern_id)


def loop_of(doc, loop_id):
    return next(l for l in doc["loops"] if l["id"] == loop_id)


# --- An independent model of the commit graph, for supplied facts --------------------------------------------------

def pathspec_matches(spec, path):
    """git's default pathspec matching: a prefix at a directory boundary, or a wildcard pattern."""
    if any(c in spec for c in "*?["):
        return fnmatch.fnmatchcase(path, spec)
    spec = spec.rstrip("/")
    return path == spec or path.startswith(spec + "/")


class Graph:
    """Commits with their parents and the files each one changes, answering the git questions the derivation asks
    the way git would, without git. This is the stand-in for a caller such as the status service, which answers
    them from the forge's API instead."""

    def __init__(self):
        self.commits = {}  # sha -> {"index", "parents", "files", "message"}

    def add(self, sha, parents, files, message=""):
        self.commits[sha] = {"index": len(self.commits), "parents": list(parents), "files": list(files),
                             "message": message}

    def resolve(self, ref):
        if ref in self.commits:
            return ref
        found = [sha for sha in self.commits if sha.startswith(ref)] if len(ref) >= 4 else []
        return found[0] if len(found) == 1 else None

    def ancestors(self, sha):
        seen, todo = set(), [sha]
        while todo:
            c = todo.pop()
            if c not in seen:
                seen.add(c)
                todo.extend(self.commits[c]["parents"])
        return seen

    def answer(self, query):
        def unknown(ref):
            return {"query": query, "value": None, "error": "fatal: Not a valid commit name %s" % ref}

        kind = query["kind"]
        if kind == "ancestor":
            a, b = self.resolve(query["commit"]), self.resolve(query["of"])
            if a is None or b is None:
                return unknown(query["commit"] if a is None else query["of"])
            return {"query": query, "value": a in self.ancestors(b), "error": None}
        if kind == "changes":
            a, b = self.resolve(query["from"]), self.resolve(query["to"])
            if a is None or b is None:
                return unknown(query["from"] if a is None else query["to"])
            between = self.ancestors(b) - self.ancestors(a)
            hits = [sha for sha in between if len(self.commits[sha]["parents"]) == 1
                    and any(pathspec_matches(p, f) for p in query["paths"] for f in self.commits[sha]["files"])]
            hits.sort(key=lambda sha: -self.commits[sha]["index"])
            return {"query": query, "value": hits, "error": None}
        if kind == "merge_base":
            a, b = self.resolve(query["a"]), self.resolve(query["b"])
            if a is None or b is None:
                return unknown(query["a"] if a is None else query["b"])
            common = self.ancestors(a) & self.ancestors(b)
            best = max(common, key=lambda sha: self.commits[sha]["index"])
            return {"query": query, "value": best, "error": None}
        raise AssertionError("a query the graph does not know: %r" % query)


def answer_all(facts, graph, foreign):
    """Answer every question the derivation asks, round after round, as a supplying caller would."""
    facts.setdefault("answers", [])
    for _ in range(10):
        pending = ls.pending_queries(facts)
        if not pending:
            return facts
        for query in pending:
            repo = query["repository"]
            if repo == facts["project"]:
                facts["answers"].append(graph.answer(query))
            else:
                on_main = foreign.get(repo, {}).get("on_main", [])
                facts["answers"].append({"query": query, "value": any(s.startswith(query["commit"]) for s in on_main),
                                         "error": None})
    raise AssertionError("the derivation kept asking new questions")


def gh_pr(repository, spec, sha_of):
    """A pull request as gh pr list --json prints it."""
    merge = spec.get("merge_sha") or (sha_of(spec["merge"]) if spec.get("merge") else None)
    return {
        "number": spec["number"],
        "title": spec["title"],
        "headRefName": spec["head"],
        "baseRefName": spec["base"],
        "state": spec["state"],
        "isDraft": spec["draft"],
        "mergeCommit": {"oid": merge} if merge else None,
        "body": spec["body"],
        "url": "https://github.com/%s/pull/%d" % (repository, spec["number"]),
        "statusCheckRollup": [{"__typename": "CheckRun", "name": "check", "workflowName": "check",
                               "status": "COMPLETED", "conclusion": spec["checks"]}],
        "files": [{"path": p, "additions": 1, "deletions": 0} for p in spec["files"]],
    }


# --- The fixture world, as a real repository -----------------------------------------------------------------------

GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
}
TEMPLATE = re.compile(r"\{sha:([A-Za-z0-9_-]+)\}")


def run_git(cwd, *args, env=None):
    full = dict(os.environ)
    full.update(GIT_ENV)
    full.update(env or {})
    r = subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True, text=True, env=full)
    if r.returncode:
        raise AssertionError("git %s failed: %s" % (" ".join(args), r.stderr))
    return r.stdout.strip()


class World:
    """world.json built as a repository at <tmp>/work with a bare origin at <tmp>/origin.git, a fake gh on PATH,
    and the served files the fixture's served-commit commands read."""

    def __init__(self, tmp):
        self.tmp = tmp
        self.spec = load(os.path.join(FIXTURES, "world.json"))
        self.work = os.path.join(tmp, "work")
        self.origin = os.path.join(tmp, "origin.git")
        self.names = {}
        self.order = []  # full shas, in creation order
        self.graph = Graph()
        self.tick = 0
        self.files = {}  # what the project tree renders to on main: path -> text

    def sha(self, name):
        return self.names[name]

    def short(self, name):
        return self.names[name][:7]

    def git(self, *args, env=None):
        return run_git(self.work, *args, env=env)

    def dated(self):
        self.tick += 1
        stamp = "%d +0000" % (1790000000 + 60 * self.tick)
        return {"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp}

    def ref(self, name):
        return self.names.get(name, name)

    def checkout(self, branch):
        if self.order:  # nothing to check out before the first commit
            self.git("checkout", "-q", branch)

    def render(self, tree):
        base = os.path.join(FIXTURES, tree)
        out = {}
        for folder, _, names in os.walk(base):
            for n in sorted(names):
                path = os.path.join(folder, n)
                rel = os.path.relpath(path, base).replace(os.sep, "/")
                with open(path, encoding="utf-8") as f:
                    out[rel] = TEMPLATE.sub(lambda m: self.short(m.group(1)), f.read())
        return out

    def write(self, files):
        for rel, text in files.items():
            path = os.path.join(self.work, rel)
            if text is None:
                os.remove(path)
                continue
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)

    def record(self, name):
        sha = self.git("rev-parse", "HEAD")
        parents = self.git("rev-list", "--parents", "-n", "1", sha).split()[1:]
        files = self.git("diff-tree", "--no-commit-id", "--name-only", "-r", sha).split() if len(parents) == 1 else []
        message = self.git("log", "-1", "--format=%B", sha)
        self.names[name] = sha
        self.order.append(sha)
        self.graph.add(sha, parents, files, message)

    def build(self):
        os.makedirs(self.work)
        self.git("init", "-q", "-b", "main")
        self.git("config", "commit.gpgsign", "false")
        for step in self.spec["steps"]:
            if "tree" in step:
                self.checkout("main")
                rendered = self.render(step["tree"])
                if step["tree"] == "project":
                    self.files = rendered
                self.write(rendered)
                self.git("add", "-A")
                self.git("commit", "-q", "-m", step["message"], env=self.dated())
                self.record(step["commit"])
            elif "commit" in step:
                self.checkout(step.get("on", "main"))
                self.write(step.get("files", {}))
                for rel, text in step.get("append", {}).items():
                    with open(os.path.join(self.work, rel), "a", encoding="utf-8") as f:
                        f.write(text)
                self.git("add", "-A")
                self.git("commit", "-q", "-m", step["message"], env=self.dated())
                self.record(step["commit"])
            elif "merge" in step:
                self.git("checkout", "-q", step.get("into", "main"))
                self.git("merge", "-q", "--no-ff", "-m", step["message"], step["from"], env=self.dated())
                self.record(step["merge"])
            elif "branch" in step:
                self.git("branch", step["branch"], self.ref(step["at"]))
            elif "label" in step:
                self.names[step["label"]] = self.git("rev-parse", step["at"])
            else:
                raise AssertionError("unknown step %r" % step)
        self.git("checkout", "-q", "main")
        self.main = self.git("rev-parse", "main")
        run_git(self.tmp, "init", "-q", "--bare", "-b", "main", self.origin)
        self.git("remote", "add", "origin", self.origin)
        self.git("push", "-q", "origin", "main", *self.spec["branches"])
        for number, name in self.spec["pull_refs"].items():
            self.git("push", "-q", "origin", "%s:refs/pull/%s/head" % (self.sha(name), number))
        self.git("fetch", "-q", "origin")
        os.makedirs(os.path.join(self.work, "served"))
        for env, name in self.spec["served"].items():
            with open(os.path.join(self.work, "served", env), "w") as f:
                f.write(self.sha(name) + "\n")
        self.setup_gh(authenticated=True)

    # The forge.

    def gh_prs(self, repository):
        if repository == PROJECT:
            specs = self.spec["pull_requests"]
        else:
            specs = self.spec["other_repositories"][repository]["pull_requests"]
        return [gh_pr(repository, s, self.sha) for s in specs]

    def setup_gh(self, authenticated):
        self.bin = os.path.join(self.tmp, "bin")
        os.makedirs(self.bin, exist_ok=True)
        shim = os.path.join(self.bin, "gh")
        with open(shim, "w") as f:
            f.write('#!/bin/sh\nexec "%s" "%s" "$@"\n' % (sys.executable, FAKE_GH))
        os.chmod(shim, 0o755)
        repositories = {PROJECT: {"pull_requests": self.gh_prs(PROJECT), "default_branch": "main",
                                  "runs": {self.main: [{"status": "completed", "conclusion": self.spec["checks_on_main"],
                                                        "workflowName": "check", "name": "check"}]}}}
        for name, other in self.spec["other_repositories"].items():
            repositories[name] = {"pull_requests": self.gh_prs(name), "default_branch": other["default_branch"],
                                  "on_main": other["on_main"]}
        self.gh_state = os.path.join(self.tmp, "gh-state.json")
        self.gh_log = os.path.join(self.tmp, "gh-calls.jsonl")
        with open(self.gh_state, "w") as f:
            json.dump({"authenticated": authenticated, "repositories": repositories}, f)
        open(self.gh_log, "w").close()

    def env(self):
        env = dict(os.environ)
        env.update(GIT_ENV)
        env["PATH"] = self.bin + os.pathsep + env.get("PATH", "")
        env["FAKE_GH_STATE"] = self.gh_state
        env["FAKE_GH_LOG"] = self.gh_log
        for key in ("GH_TOKEN", "GITHUB_TOKEN", "GH_REPO", "GH_HOST"):
            env.pop(key, None)
        return env

    def gh_calls(self):
        with open(self.gh_log) as f:
            return [json.loads(line) for line in f if line.strip()]

    # The terminal's way: gather from the repository.

    def gather(self):
        return ls.gather(self.work, project=PROJECT, as_of=self.spec["as_of"], env=self.env())

    def cli(self, *args, stdin=None):
        return subprocess.run([sys.executable, SCRIPT] + list(args), cwd=self.work, env=self.env(),
                              capture_output=True, text=True, input=stdin)

    # The status service's way: supply the facts, and answer the git questions without git.

    def supplied(self):
        loop_md = self.files["LOOP.md"]
        served = {"main": self.main}
        served.update({env: self.sha(name) for env, name in self.spec["served"].items()})
        environments = []
        for row in ls.environment_rows(loop_md):
            if row["error"]:
                environments.append({"name": row["name"], "served": None, "error": row["error"]})
            else:
                environments.append({"name": row["name"], "served": served[row["name"]], "error": None})
        on_main = self.graph.ancestors(self.main)
        trailers, merges = [], []
        for sha in reversed(self.order):
            if sha not in on_main:
                continue
            refs = re.findall(r"(?m)^Concern: (\S+)$", self.graph.commits[sha]["message"])
            if refs:
                trailers.append({"sha": sha, "concerns": refs})
        first_parent, sha = [], self.main
        while sha:
            first_parent.append(sha)
            parents = self.graph.commits[sha]["parents"]
            sha = parents[0] if parents else None
        for sha in first_parent:
            subject = self.graph.commits[sha]["message"].splitlines()[0]
            if subject.startswith("Merge pull request #"):
                merges.append({"sha": sha, "subject": subject})
        heads = {"main": self.main}
        heads.update({b: self.git("rev-parse", b) for b in self.spec["branches"]})
        facts = {
            "facts_version": ls.FACTS_VERSION,
            "project": PROJECT,
            "as_of": self.spec["as_of"],
            "files": {p: t for p, t in self.files.items() if p == "LOOP.md" or p.startswith("docs/loops/")},
            "main": {"branch": "main", "sha": self.main, "error": None},
            "ci": {"commit": self.main, "state": self.spec["checks_on_main"], "error": None},
            "environments": environments,
            "pull_requests": [{"repository": r, "items": [ls.normalize_pr(p, r) for p in self.gh_prs(r)],
                               "error": None} for r in [PROJECT] + sorted(self.spec["other_repositories"])],
            "branches": {"heads": heads, "error": None},
            "trailers": {"commits": trailers, "error": None},
            "merges": {"commits": merges, "error": None},
            "repositories": [{"repository": r, "default_branch": o["default_branch"], "error": None}
                             for r, o in sorted(self.spec["other_repositories"].items())],
            "loop_document_checks": [{"repository": PROJECT, "number": 9, "head": self.sha("record-1"), "ok": False,
                                      "failures": ["FAIL: changes a file outside docs/loops/: LOOP.md"],
                                      "error": None}],
            "answers": [],
        }
        return answer_all(facts, self.graph, self.spec["other_repositories"])


@unittest.skipUnless(shutil.which("git") and shutil.which("sh"), "needs git and sh")
class WorldTest(unittest.TestCase):
    """C1 for the whole fixture world at once, and C3: gathered and supplied facts give the same document."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="loop-status-world-")
        cls.world = World(cls.tmp)
        cls.world.build()
        cls.expected = load(os.path.join(FIXTURES, "expected.json"))
        cls.facts = cls.world.gather()
        cls.doc = ls.derive(cls.facts)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_document_validates(self):
        check_document(self, self.doc)

    def test_every_concern_gets_the_tables_state(self):
        self.assertEqual(states(self.doc), self.expected["concerns"])

    def test_every_loop_gets_step_5s_state(self):
        self.assertEqual({l["id"]: l["state"] for l in self.doc["loops"]}, self.expected["loops"])

    def test_the_world_holds_every_state(self):
        found = set(states(self.doc).values())
        self.assertEqual(found, set(ls.CONCERN_STATES))
        self.assertEqual({l["state"] for l in self.doc["loops"]}, set(ls.LOOP_STATES))

    def test_the_queue_is_every_kind_most_unblocking_first(self):
        got = [{"id": i["id"], "kind": i["kind"], "unblocks": i["unblocks"]} for i in self.doc["queue"]]
        self.assertEqual(got, self.expected["queue"])
        for item in self.doc["queue"]:
            self.assertIsNone(item["waits_on"], "addressing is addressed-to-people's")
            self.assertEqual(item["visible_to"], [])

    def test_agents_can_start(self):
        self.assertEqual(self.doc["agents_can_start"], self.expected["agents_can_start"])

    def test_drift(self):
        self.assertEqual(sorted(d["where"] for d in self.doc["drift"]), self.expected["drift"])

    def test_missing_facts(self):
        self.assertEqual([m["fact"] for m in self.doc["missing"]], self.expected["missing"])

    def test_inputs_name_the_facts(self):
        scheduler = concern(self.doc, "reports/scheduler")
        self.assertEqual(scheduler["inputs"]["served"], {
            "environment": "production", "commit": self.world.sha("worker-merge"), "error": None, "serves": False})
        self.assertEqual(scheduler["inputs"]["commits"], [self.world.sha("scheduler-1")])
        self.assertEqual([(p["number"], p["on_main"]) for p in scheduler["inputs"]["prs"]], [(4, True)])
        self.assertEqual(scheduler["inputs"]["branch"], {"name": "reports/scheduler", "exists": False})
        audit = concern(self.doc, "reports/audit-trail")
        self.assertEqual(audit["inputs"]["served"]["serves"], None)
        self.assertIn("TODO(owner)", audit["inputs"]["served"]["error"])
        self.assertTrue(any("sandbox" in m for m in audit["inputs"]["missing"]))

    def test_the_question_item_carries_what_questions_py_reads(self):
        item = next(i for i in self.doc["queue"] if i["id"] == "reports/dashboard/Q1")
        self.assertEqual(item["detail"]["options"][0]["text"], "The reports database")
        self.assertEqual(item["detail"]["recommendation"], "The reports database")
        self.assertEqual(item["detail"]["default"],
                         "The reports database, until the page needs more than one sample a minute")
        self.assertEqual(item["detail"]["blocks"], ["C1"])
        prose = next(i for i in self.doc["queue"] if i["id"] == "reports/Q2")
        self.assertEqual((prose["detail"]["options"], prose["detail"]["recommendation"]), ([], None))

    def test_the_read_only_items_carry_their_facts(self):
        items = {i["id"]: i for i in self.doc["queue"]}
        proof = items["reports/queue/C2"]["detail"]
        self.assertEqual((proof["environment"], proof["missing"], proof["supplied_by"], proof["command"]),
                         ("staging", "a 10,000-job load on staging", "the owner", "/loop-prove reports/queue staging"))
        worker = items["reports/worker/C2"]["detail"]
        self.assertEqual((worker["contradicts"], worker["escalates"]), ("reports/D1", True))
        self.assertEqual(worker["evidence"]["verdict"], "CONTRADICTS")
        importer = items["reports/importer/C1"]["detail"]
        self.assertFalse(importer["escalates"])
        self.assertIsNone(importer["evidence"]["commit"])
        refused = items["example/reports#9"]["detail"]
        self.assertEqual(refused["failures"], ["FAIL: changes a file outside docs/loops/: LOOP.md"])
        ship = items["ship/production"]["detail"]
        self.assertEqual(ship, {"environment": "production",
                                "manual_steps": ["the SMTP password in production's secret store (secrets)"]})

    # C3.

    def test_supplied_facts_give_the_same_document(self):
        supplied = self.world.supplied()
        self.assertEqual(ls.derive(supplied), self.doc)

    def test_a_facts_document_derives_the_same_after_a_round_trip(self):
        self.assertEqual(ls.derive(json.loads(json.dumps(self.facts))), self.doc)

    def test_the_command_line_gives_the_same_document_every_way(self):
        args = ["--project", PROJECT, "--as-of", self.world.spec["as_of"]]
        both = self.world.cli("--json", *args)
        self.assertEqual(both.returncode, 0, both.stderr)
        self.assertEqual(json.loads(both.stdout), self.doc)
        gathered = self.world.cli("gather", *args)
        self.assertEqual(gathered.returncode, 0, gathered.stderr)
        path = os.path.join(self.tmp, "facts.json")
        with open(path, "w") as f:
            f.write(gathered.stdout)
        derived = self.world.cli("derive", "--facts", path, "--json")
        self.assertEqual(derived.returncode, 0, derived.stderr)
        self.assertEqual(json.loads(derived.stdout), self.doc)
        piped = self.world.cli("derive", "--facts", "-", "--json", stdin=gathered.stdout)
        self.assertEqual(json.loads(piped.stdout), self.doc)
        board = self.world.cli("derive", "--facts", path)
        self.assertEqual(board.stdout, ls.board(self.doc))

    def test_gathering_twice_gives_the_same_document(self):
        self.assertEqual(ls.derive(self.world.gather()), self.doc)

    def test_gathering_reads_only_what_it_may(self):
        commands = [entry["command"] for entry in self.facts["log"]]
        self.assertFalse([c for c in commands if "served.sh vault" in c], "vault is not readable by agents")
        self.assertFalse([c for c in commands if "served.sh <URL>" in c], "a TODO row is not run")
        for call in self.world.gh_calls():
            self.assertIn(call[0], ("pr", "run", "api"), call)
            if call[0] == "api":
                self.assertTrue(call[1].startswith("repos/example/tools"), call)
        vault = next(e for e in self.facts["environments"] if e["name"] == "vault")
        self.assertIn("may not read", vault["error"])

    def test_the_documents_are_read_from_main_not_the_working_tree(self):
        path = os.path.join(self.world.work, "docs", "loops", "reports", "exporter.md")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text.replace("ships-to: production", "parked: D9"))
            self.assertEqual(states(ls.derive(self.world.gather()))["reports/exporter"], "ready")
        finally:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)

    def test_without_gh_work_is_linked_from_git_alone(self):
        self.world.setup_gh(authenticated=False)
        try:
            doc = ls.derive(self.world.gather())
        finally:
            self.world.setup_gh(authenticated=True)
        check_document(self, doc)
        got = states(doc)
        # Trailers and merge subjects still put work on main; whether anything is open cannot be read.
        self.assertEqual(got["reports/metrics"], "stale")
        self.assertEqual(got["reports/scheduler"], "merged")
        self.assertEqual(got["reports/exporter"], "unknown")
        self.assertEqual(got["reports/contract"], "unknown", "its claim holds by CI, which cannot be read")
        self.assertEqual(got["reports/dashboard"], "open", "a question needs only the loop's files")
        self.assertEqual(got["reports/worker"], "contradicted")
        self.assertEqual(loop_of(doc, "search")["state"], "unknown")
        self.assertIn("pull requests", [m["fact"] for m in doc["missing"]])
        self.assertTrue(any(m["fact"].startswith("checks on main") for m in doc["missing"]))

    def test_the_board(self):
        text = ls.board(self.doc)
        self.assertIn("reports · 16 concerns · main %s" % self.world.main[:7], text)
        self.assertIn("staging serves %s" % self.world.short("staging-build"), text)
        self.assertRegex(text, r"(?m)^scheduler +merged +.+ +/loop-ship production$")
        self.assertIn("Needs you (8), most unblocking first", text)
        self.assertIn("Agents can start now (6)", text)
        self.assertIn("Record (2), on your yes", text)
        self.assertIn("search · backlog", text)
        one = ls.board(self.doc, "reports/scheduler")
        self.assertIn("state     merged", one)
        self.assertIn(self.world.sha("scheduler-merge")[:7], one)
        self.assertNotIn("dashboard", one)
        with self.assertRaises(ValueError):
            ls.board(self.doc, "reports/nothing")


# --- One small world per row of the table and per definition -------------------------------------------------------

LOOP_MD = """# LOOP.md

## 3. Environments

| Environment | Where | Agents may read | Agents may write | Deployed by | Served commit: a command that prints its SHA | Verify with |
| --- | --- | --- | --- | --- | --- | --- |
| main | main | yes | no | owner | `git rev-parse origin/main` | |
| staging | staging | yes | no | owner | `sh served.sh staging` | |
| production | production | yes | no | owner | `sh served.sh production` | |
"""


def sha_of(name):
    return hashlib.sha1(name.encode()).hexdigest()


def concern_md(needs="[]", touches="[src/x/]", ships_to="staging", effects="[]", extra="", claims=None,
               evidence=(), decisions=(), questions=(), shipped=""):
    front = ["needs: %s" % needs, "touches: %s" % touches, "effects: %s" % effects]
    if ships_to is not None:
        front.append("ships-to: %s" % ships_to)
    if extra:
        front.append(extra)
    claims = ["- **C1** It works. Prove: a run, on staging."] if claims is None else list(claims)
    lines = ["---"] + front + ["---", "# A concern that does one thing", "", "## Done when", ""] + claims
    lines += ["", "## Decisions", "", "| # | Decision | Decided by, date | Closes |", "| --- | --- | --- | --- |"]
    lines += list(decisions)
    lines += ["", "## Questions", "", "| # | Question | Blocks | Default if unanswered |", "| --- | --- | --- | --- |"]
    lines += list(questions)
    lines += ["", "## Evidence", ""] + list(evidence) + ["", "## Shipped", "", shipped]
    return "\n".join(lines) + "\n"


def readme_md(title="A loop", front="", goals=(), decisions=(), questions=(), shipped=""):
    lines = (["---", front, "---"] if front else []) + ["# %s" % title, "", "## Goals", ""] + list(goals)
    lines += ["", "## Shared decisions", "", "| # | Decision | Decided by, date | Notes |", "| --- | --- | --- | --- |"]
    lines += list(decisions)
    lines += ["", "## Questions", "", "| # | Question | Blocks | Default if unanswered |", "| --- | --- | --- | --- |"]
    lines += list(questions)
    lines += ["", "## Evidence", "", "## Shipped", "", shipped]
    return "\n".join(lines) + "\n"


class Mini:
    """A small project for one row of the table: a loop or two, a linear main with pull requests merged into it,
    and environments that serve named commits. Its git questions are answered by a Graph."""

    def __init__(self):
        self.graph = Graph()
        self.files = {"LOOP.md": LOOP_MD}
        self.prs = {PROJECT: []}
        self.pr_error = {}
        self.foreign = {}
        self.branches = {}
        self.trailers = []
        self.merges = []
        self.checks = []
        self.ci, self.ci_error = "success", None
        self.served = {}
        self.env_error = {}
        self.main = None
        self.root = self.commit("root")
        for env in ("staging", "production"):
            self.served[env] = self.root

    def add(self, name, parents, files, message=None):
        sha = sha_of(name)
        self.graph.add(sha, parents, files, message or name)
        return sha

    def commit(self, name, files=("README.md",)):
        """A commit on main; returns its sha."""
        self.main = self.add(name, [self.main] if self.main else [], files)
        return self.main

    def detached(self, name, parent, files=("README.md",)):
        """A commit that is not on main, such as one on a branch; returns its sha."""
        return self.add(name, [parent], files)

    def loop(self, loop_id, **readme):
        self.files["docs/loops/%s/README.md" % loop_id] = readme_md(**readme)

    def concern(self, ref, text):
        loop_id, concern_id = ref.split("/")
        if "docs/loops/%s/README.md" % loop_id not in self.files:
            self.loop(loop_id)
        self.files["docs/loops/%s/%s.md" % (loop_id, concern_id)] = text

    def land(self, ref, number, files=("src/x/a.py",), trailer=False):
        """A pull request for ref merged into main, as GitHub merges one: a branch commit and a merge commit.
        Returns the merge commit's sha."""
        base = self.main
        work = self.detached("%s-%d-work" % (ref, number), base, files=files)
        subject = "Merge pull request #%d from example/%s" % (number, ref)
        self.main = self.add("%s-%d-merge" % (ref, number), [base, work], [], subject)
        self.merges.insert(0, {"sha": self.main, "subject": subject})
        if trailer:
            self.trailers.insert(0, {"sha": work, "concerns": [ref]})
        self.pr(ref, number, "MERGED", merge_sha=self.main, files=files)
        return self.main

    def pr(self, head, number, state, merge_sha=None, base="main", draft=False, checks="SUCCESS", body=None,
           repository=PROJECT, files=("src/x/a.py",)):
        body = "Does the thing.\n\nConcern: %s\n" % head if body is None else body
        spec = {"number": number, "title": "Pull request %d" % number, "head": head, "base": base, "state": state,
                "draft": draft, "merge_sha": merge_sha, "checks": checks, "files": list(files), "body": body}
        self.prs.setdefault(repository, []).append(gh_pr(repository, spec, sha_of))

    def serve(self, env, sha=None):
        """env serves main as it is now, or the given commit."""
        self.served[env] = sha or self.main

    def facts(self):
        environments = []
        for row in ls.environment_rows(self.files["LOOP.md"]):
            name = row["name"]
            if row["error"]:
                environments.append({"name": name, "served": None, "error": row["error"]})
            elif name == "main":
                environments.append({"name": name, "served": self.main, "error": None})
            elif name in self.env_error:
                environments.append({"name": name, "served": None, "error": self.env_error[name]})
            else:
                environments.append({"name": name, "served": self.served[name], "error": None})
        facts = {
            "facts_version": ls.FACTS_VERSION,
            "project": PROJECT,
            "as_of": AS_OF,
            "files": dict(self.files),
            "main": {"branch": "main", "sha": self.main, "error": None},
            "ci": {"commit": self.main, "state": self.ci, "error": self.ci_error},
            "environments": environments,
            "pull_requests": [{"repository": r, "items": [] if r in self.pr_error else
                               [ls.normalize_pr(p, r) for p in items], "error": self.pr_error.get(r)}
                              for r, items in sorted(self.prs.items())],
            "branches": {"heads": dict(self.branches, main=self.main), "error": None},
            "trailers": {"commits": list(self.trailers), "error": None},
            "merges": {"commits": list(self.merges), "error": None},
            "repositories": [{"repository": r, "default_branch": "main", "error": None} for r in sorted(self.foreign)],
            "loop_document_checks": list(self.checks),
            "answers": [],
        }
        return answer_all(facts, self.graph, self.foreign)

    def derive(self, test):
        doc = ls.derive(self.facts())
        check_document(test, doc)
        return doc


class TableTest(unittest.TestCase):
    """C1: one case per row of the derivation table, top to bottom, and per definition under it."""

    def derive(self, mini):
        return mini.derive(self)

    def state(self, mini, ref="loop/thing"):
        c = concern(self.derive(mini), ref)
        return c["state"], c

    # Rows.

    def test_parked_wins_over_everything_below_it(self):
        m = Mini()
        m.concern("loop/thing", concern_md(extra="parked: D1",
                                           decisions=["| D1 | Parked until the vendor ships an API. | Ana, 2026-10-01 | |"],
                                           evidence=["- 2026-10-02 · C1 · CONTRADICTS · rung 1 · staging @? · broke"]))
        state, c = self.state(m)
        self.assertEqual(state, "parked")
        self.assertIn("Parked until the vendor ships an API", c["next"])

    def test_contradicted_until_a_decision_is_dated_after_it(self):
        m = Mini()
        m.land("loop/thing", 1)
        m.serve("staging")
        line = "- 2026-10-10 · C1 · CONTRADICTS · rung 1 · staging @%s · p95 41 s" % m.main[:7]
        m.concern("loop/thing", concern_md(evidence=[line],
                                           decisions=["| D1 | Use one worker. | Ana, 2026-10-09 | |"]))
        state, c = self.state(m)
        self.assertEqual(state, "contradicted")
        self.assertEqual(c["next"], "/loop-design loop/thing")
        m.concern("loop/thing", concern_md(evidence=[line], decisions=[
            "| D1 | Use one worker. | Ana, 2026-10-09 | |", "| D2 | Use a pool of four. | Ana, 2026-10-11 | |"]))
        self.assertEqual(self.state(m)[0], "shipped", "a later decision answers the contradiction")

    def test_a_shared_decision_naming_the_concern_after_it_answers_a_contradiction(self):
        m = Mini()
        line = "- 2026-10-10 · C1 · CONTRADICTS · rung 1 · staging @? · broke"
        m.concern("loop/thing", concern_md(evidence=[line]))
        m.concern("loop/other", concern_md())
        m.loop("loop", decisions=["| D1 | `other` uses a pool. | Ana, 2026-10-11 | |"])
        self.assertEqual(self.state(m)[0], "contradicted", "a later decision about another concern does not count")
        m.loop("loop", decisions=["| D1 | `thing` uses a pool. | Ana, 2026-10-11 | |"])
        self.assertEqual(self.state(m)[0], "ready")

    def test_open_by_an_unanswered_question_that_blocks_a_claim(self):
        m = Mini()
        m.concern("loop/thing", concern_md(questions=["| Q1 | Which store? | C1 | The database |"]))
        state, c = self.state(m)
        self.assertEqual(state, "open")
        self.assertIn("Q1", c["reason"])
        m.concern("loop/thing", concern_md(questions=["| Q1 | Which store? | | The database |"]))
        self.assertEqual(self.state(m)[0], "ready", "a question that blocks no claim does not open it")
        m.concern("loop/thing", concern_md(questions=["| ~~Q1~~ | ~~Which store?~~ → D1 | | |"]))
        self.assertEqual(self.state(m)[0], "ready")

    def test_open_by_a_loop_question_that_blocks_the_concern(self):
        m = Mini()
        m.concern("loop/thing", concern_md())
        m.loop("loop", questions=["| Q4 | Who runs it? | `thing`, G1 | Nobody |"])
        state, c = self.state(m)
        self.assertEqual(state, "open")
        self.assertIn("loop/Q4", c["reason"])

    def test_open_by_a_superseded_decision_in_needs(self):
        m = Mini()
        m.loop("loop", decisions=["| ~~D1~~ | ~~One worker.~~ | Ana, 2026-10-01 | Superseded by D2 |",
                                  "| D2 | A pool. | Ana, 2026-10-02 | |"])
        m.concern("loop/thing", concern_md(needs="[loop/D1]"))
        self.assertEqual(self.state(m)[0], "open")
        m.concern("loop/thing", concern_md(needs="[loop/D2]"))
        self.assertEqual(self.state(m)[0], "ready")
        m.concern("loop/thing", concern_md(needs="[D2]"))
        self.assertEqual(self.state(m)[0], "ready", "a bare D# in needs is the concern's own loop's")

    def test_open_by_an_incomplete_contract_only_while_nothing_is_built(self):
        for name, text in {"touches": concern_md(touches="[]"), "ships-to": concern_md(ships_to=None),
                           "Done when": concern_md(claims=[])}.items():
            m = Mini()
            m.concern("loop/thing", text)
            state, c = self.state(m)
            with self.subTest(lacks=name):
                self.assertEqual(state, "open")
                self.assertIn(name, c["reason"])
        m = Mini()
        m.concern("loop/thing", concern_md(touches="[]"))
        m.branches["loop/thing"] = m.main
        doc = self.derive(m)
        self.assertEqual(concern(doc, "loop/thing")["state"], "building",
                         "a built concern is never shown open because of a gap in its contract")
        self.assertTrue(any("lacks touches" in d["finding"] for d in doc["drift"]))

    def test_blocked_while_a_need_is_not_done(self):
        m = Mini()
        m.concern("loop/base", concern_md(questions=["| Q1 | Which? | C1 | This |"]))
        m.concern("loop/thing", concern_md(needs="[base]"))
        state, c = self.state(m)
        self.assertEqual(state, "blocked")
        self.assertEqual(c["next"], "/loop-design loop/base", "a blocked concern's next is its need's")
        m.concern("loop/thing", concern_md(needs="[missing]"))
        self.assertEqual(self.state(m)[0], "blocked", "a need that does not exist is not done")
        m.concern("other/thing", concern_md(needs="[loop/base]"))
        self.assertEqual(self.state(m, "other/thing")[0], "blocked", "needs reach across loops")

    def test_ready_when_nothing_is_built_and_every_need_is_done(self):
        m = Mini()
        m.land("loop/base", 1)
        m.concern("loop/base", concern_md(ships_to="main", claims=["- **C1** Holds. Prove: unit tests, in CI on main."]))
        m.concern("loop/thing", concern_md(needs="[base]"))
        state, c = self.state(m)
        self.assertEqual(state, "ready")
        self.assertEqual(c["next"], "/loop-build loop/thing")
        m.pr("loop/thing", 2, "CLOSED", checks="FAILURE")
        self.assertEqual(self.state(m)[0], "ready", "a pull request closed without merging is not work")

    def test_building_while_a_pr_is_open_or_the_branch_exists(self):
        m = Mini()
        m.concern("loop/thing", concern_md())
        m.pr("loop/thing", 2, "OPEN", draft=True)
        state, c = self.state(m)
        self.assertEqual(state, "building")
        self.assertIn("draft", c["next"])
        m = Mini()
        m.concern("loop/thing", concern_md())
        m.branches["loop/thing"] = m.main
        state, c = self.state(m)
        self.assertEqual(state, "building")
        self.assertIn("no pull request", c["next"])
        m = Mini()
        m.concern("loop/thing", concern_md())
        m.pr("loop/other-branch", 3, "OPEN", body="Work.\n\nConcern: loop/thing\n")
        self.assertEqual(self.state(m)[0], "building", "a Concern line in the body links a PR")

    def test_a_review_item_needs_green_checks_and_the_proof(self):
        proof = "## How it was proven before the merge\n\n- [x] C1: HOLDS (rung 5, local)\n\nConcern: loop/thing\n"
        for checks, draft, body, queued in (("SUCCESS", False, proof, True), ("FAILURE", False, proof, False),
                                            ("PENDING", False, proof, False), ("SUCCESS", True, proof, False),
                                            ("SUCCESS", False, "No proof.\n\nConcern: loop/thing\n", False)):
            m = Mini()
            m.concern("loop/thing", concern_md())
            m.pr("loop/thing", 2, "OPEN", draft=draft, checks=checks, body=body)
            doc = self.derive(m)
            reviews = [i for i in doc["queue"] if i["kind"] == "review"]
            with self.subTest(checks=checks, draft=draft, proof="How it" in body):
                self.assertEqual(bool(reviews), queued)
                if queued:
                    self.assertEqual(reviews[0]["detail"]["proof"], "- [x] C1: HOLDS (rung 5, local)")

    def test_merged_while_ships_to_does_not_serve_it(self):
        m = Mini()
        m.land("loop/thing", 1)
        m.concern("loop/thing", concern_md(effects="[a migration on shared data]"))
        state, c = self.state(m)
        self.assertEqual(state, "merged")
        self.assertEqual(c["next"], "/loop-ship staging")
        self.assertIs(c["inputs"]["served"]["serves"], False)
        ship = [i for i in self.derive(m)["queue"] if i["kind"] == "ship"]
        self.assertEqual(ship[0]["detail"], {"environment": "staging", "manual_steps": ["a migration on shared data"]})
        self.assertIsNone(ship[0]["gate"])

    def test_shipped_while_a_claim_has_no_current_holds(self):
        m = Mini()
        m.land("loop/thing", 1)
        m.serve("staging")
        m.concern("loop/thing", concern_md())
        state, c = self.state(m)
        self.assertEqual(state, "shipped")
        self.assertEqual(c["next"], "/loop-prove loop/thing staging")
        self.assertIs(c["claims"][0]["current_holds"], False)

    def test_stale_when_touches_changed_since_the_proof(self):
        m = Mini()
        m.land("loop/thing", 1)
        proof = m.main
        m.commit("later", files=("src/x/b.py",))
        m.serve("staging")
        m.concern("loop/thing", concern_md(evidence=["- 2026-10-10 · C1 · HOLDS · rung 1 · staging @%s · ok" % proof[:7]]))
        state, c = self.state(m)
        self.assertEqual(state, "stale")
        self.assertIn(sha_of("later")[:7], c["reason"])
        self.assertIs(c["claims"][0]["current_holds"], False)
        m.concern("loop/thing", concern_md(touches="[src/y/]", evidence=[
            "- 2026-10-10 · C1 · HOLDS · rung 1 · staging @%s · ok" % proof[:7]]))
        self.assertEqual(self.state(m)[0], "done", "a change outside touches leaves the HOLDS current")

    def test_stale_when_a_decision_in_needs_was_superseded(self):
        m = Mini()
        m.land("loop/thing", 1)
        m.serve("staging")
        m.loop("loop", decisions=["| ~~D1~~ | ~~One worker.~~ | Ana, 2026-10-01 | Superseded by D2 |"])
        m.concern("loop/thing", concern_md(needs="[loop/D1]", evidence=[
            "- 2026-10-10 · C1 · HOLDS · rung 1 · staging @%s · ok" % m.main[:7]]))
        doc = self.derive(m)
        self.assertEqual(concern(doc, "loop/thing")["state"], "stale")
        self.assertTrue(any("superseded" in d["finding"] for d in doc["drift"]))

    def test_done_when_every_claim_has_a_current_holds(self):
        m = Mini()
        m.land("loop/thing", 1)
        m.serve("staging")
        line = "- 2026-10-10 · C1 · HOLDS · rung 1 · staging @%s · ok" % m.main[:7]
        m.concern("loop/thing", concern_md(evidence=[line]))
        doc = self.derive(m)
        self.assertEqual(concern(doc, "loop/thing")["state"], "done")
        self.assertIs(concern(doc, "loop/thing")["claims"][0]["current_holds"], True)
        self.assertEqual([i["id"] for i in doc["queue"]], ["record/loop", "record/loop/thing"])
        m.concern("loop/thing", concern_md(evidence=[line], shipped="2026-10-11, to staging."))
        self.assertIsNone(self.state(m)[1]["next"], "a Shipped note is offered only once")

    def test_no_row_matches_a_pr_merged_outside_main_without_a_branch(self):
        m = Mini()
        side = m.detached("side", m.root)
        m.concern("loop/thing", concern_md())
        m.pr("loop/thing", 2, "MERGED", base="loop/base", merge_sha=side)
        state, c = self.state(m)
        self.assertEqual(state, "unknown")
        self.assertIn("no row", c["reason"].lower())
        m.branches["loop/thing"] = side
        self.assertEqual(self.state(m)[0], "building", "its branch still exists, and none of its work is on main")

    # Definitions.

    def test_serves_needs_every_merge_commit(self):
        m = Mini()
        first = m.land("loop/thing", 1)
        m.land("loop/thing", 2)
        m.serve("staging", first)
        m.concern("loop/thing", concern_md())
        state, c = self.state(m)
        self.assertEqual(state, "merged")
        m.serve("staging")
        self.assertEqual(self.state(m)[0], "shipped")

    def test_for_ships_to_main_the_head_of_main_serves_it(self):
        m = Mini()
        m.land("loop/thing", 1)
        m.concern("loop/thing", concern_md(ships_to="main"))
        state, c = self.state(m)
        self.assertEqual(state, "shipped")
        self.assertEqual(c["inputs"]["served"]["commit"], m.main)

    def test_github_merged_is_not_enough(self):
        """A PR merged into another branch is not merged until its merge commit is on main."""
        m = Mini()
        side = m.detached("side", m.root)
        m.concern("loop/thing", concern_md())
        m.pr("loop/thing", 2, "MERGED", base="loop/base", merge_sha=side)
        m.branches["loop/thing"] = side
        state, c = self.state(m)
        self.assertEqual(state, "building")
        self.assertIs(c["inputs"]["prs"][0]["on_main"], False)

    def test_a_current_holds_is_on_ships_to(self):
        m = Mini()
        m.land("loop/thing", 1)
        m.serve("staging")
        m.serve("production")
        m.concern("loop/thing", concern_md(ships_to="production", evidence=[
            "- 2026-10-10 · C1 · HOLDS · rung 1 · staging @%s · ok on staging" % m.main[:7]]))
        self.assertEqual(self.state(m)[0], "shipped", "a HOLDS on staging is not one on production")

    def test_a_current_holds_cites_an_ancestor_of_the_served_commit(self):
        m = Mini()
        m.land("loop/thing", 1)
        m.serve("staging")
        elsewhere = m.detached("elsewhere", m.root, files=("src/x/c.py",))
        m.concern("loop/thing", concern_md(evidence=[
            "- 2026-10-10 · C1 · HOLDS · rung 1 · staging @%s · ok" % elsewhere[:7]]))
        self.assertEqual(self.state(m)[0], "shipped")

    def test_the_latest_line_is_the_verdict(self):
        m = Mini()
        m.land("loop/thing", 1)
        m.serve("staging")
        sha = m.main[:7]
        m.concern("loop/thing", concern_md(evidence=[
            "- 2026-10-10 · C1 · HOLDS · rung 1 · staging @%s · ok" % sha,
            "- 2026-10-11 · C1 · UNPROVEN · rung 1 · staging @%s · the rerun could not reach staging" % sha]))
        state, c = self.state(m)
        self.assertEqual(state, "shipped", "a claim with an UNPROVEN after its HOLDS is not proven")
        m.concern("loop/thing", concern_md(evidence=[
            "- 2026-10-10 · C1 · UNPROVEN · rung 1 · staging @%s · not yet" % sha]))
        self.assertEqual(self.state(m)[0], "shipped", "a claim with only UNPROVEN lines is not proven")

    def test_a_line_at_question_mark_never_holds_but_still_contradicts(self):
        m = Mini()
        m.land("loop/thing", 1)
        m.serve("staging")
        m.concern("loop/thing", concern_md(evidence=["- 2026-10-10 · C1 · HOLDS · rung 1 · staging @? · migrated"]))
        state, c = self.state(m)
        self.assertEqual(state, "shipped")
        self.assertIsNone(c["claims"][0]["evidence"][0]["commit"])
        m.concern("loop/thing", concern_md(evidence=["- 2026-10-10 · C1 · CONTRADICTS · rung 6 · staging @? · migrated"]))
        self.assertEqual(self.state(m)[0], "contradicted")

    def test_a_struck_claim_counts_for_nothing(self):
        m = Mini()
        m.land("loop/thing", 1)
        m.serve("staging")
        sha = m.main[:7]
        m.concern("loop/thing", concern_md(
            claims=["- **C1** It works. Prove: a run, on staging.", "- ~~**C2** It flies.~~ Superseded by C1."],
            evidence=["- 2026-10-09 · C2 · CONTRADICTS · rung 1 · staging @%s · it does not fly" % sha,
                      "- 2026-10-10 · C1 · HOLDS · rung 1 · staging @%s · ok" % sha]))
        state, c = self.state(m)
        self.assertEqual(state, "done")
        self.assertEqual([(x["id"], x["struck"], x["current_holds"]) for x in c["claims"]],
                         [("C1", False, True), ("C2", True, None)])

    def test_a_claim_proven_in_ci_on_main_holds_at_rung_5_when_ci_is_green(self):
        ci_claim = ["- **C1** Holds. Prove: unit tests, in CI on main."]
        for ci, error, expected in (("success", None, "done"), ("failure", None, "shipped"),
                                    ("pending", None, "shipped"), ("none", None, "shipped"),
                                    ("unknown", "gh is not authenticated", "unknown")):
            m = Mini()
            m.land("loop/thing", 1)
            m.ci, m.ci_error = ci, error
            m.concern("loop/thing", concern_md(ships_to="main", claims=ci_claim))
            with self.subTest(ci=ci):
                self.assertEqual(self.state(m)[0], expected)
        m = Mini()
        m.land("loop/thing", 1)
        m.concern("loop/thing", concern_md(ships_to="main", claims=[
            "- **C1** Holds. Prove: the API tests, in CI on main, then a dispatch, on staging."]))
        self.assertEqual(self.state(m)[0], "shipped", "a Prove that goes on past CI needs its line")

    def test_a_pr_merged_in_another_repository_counts_on_that_repositorys_main(self):
        """command-center/D19, with its fixture row."""
        merge = "5a1f0e2d9c8b7a6f5e4d3c2b1a0f9e8d7c6b5a4f"
        for on_main, expected in ((True, "done"), (False, "unknown")):
            m = Mini()
            m.foreign["example/tools"] = {"on_main": [merge] if on_main else []}
            m.pr("sync-templates", 11, "MERGED", repository="example/tools", merge_sha=merge, body="Sync.\n")
            m.concern("loop/thing", concern_md(ships_to="main", touches="[example/tools:sync/]",
                                               extra="prs: [example/tools#11]",
                                               claims=["- **C1** Syncs. Prove: the sync tests, in CI on main."]))
            state, c = self.state(m)
            with self.subTest(on_main=on_main):
                self.assertEqual(state, expected)
                self.assertEqual(c["inputs"]["prs"][0]["repository"], "example/tools")
                self.assertIs(c["inputs"]["prs"][0]["on_main"], on_main)
                self.assertIs(c["inputs"]["served"]["serves"], True if on_main else False)

    def test_unknown_when_the_served_commit_cannot_be_read(self):
        m = Mini()
        m.land("loop/thing", 1)
        m.env_error["staging"] = "`sh served.sh staging` exited 1: no build answers for staging"
        m.concern("loop/thing", concern_md())
        state, c = self.state(m)
        self.assertEqual(state, "unknown")
        self.assertTrue(any("staging" in x for x in c["inputs"]["missing"]))
        self.assertIsNone(c["claims"][0]["current_holds"])

    def test_unknown_when_ships_to_names_no_row(self):
        m = Mini()
        m.land("loop/thing", 1)
        m.concern("loop/thing", concern_md(ships_to="production/app"))
        state, c = self.state(m)
        self.assertEqual(state, "unknown")
        self.assertIn("no row", c["inputs"]["served"]["error"])
        m = Mini()
        m.concern("loop/thing", concern_md(ships_to="production/app"))
        self.assertEqual(self.state(m)[0], "ready", "a row that does not exist yet matters only once merged")

    def test_unknown_when_pull_requests_cannot_be_read(self):
        m = Mini()
        m.pr_error[PROJECT] = "gh: not authenticated"
        m.concern("loop/thing", concern_md())
        m.concern("loop/asked", concern_md(questions=["| Q1 | Which? | C1 | This |"]))
        doc = self.derive(m)
        self.assertEqual(concern(doc, "loop/thing")["state"], "unknown", "ready and building cannot be told apart")
        self.assertEqual(concern(doc, "loop/asked")["state"], "open", "a question needs only the loop's files")
        m.branches["loop/thing"] = m.main
        self.assertEqual(self.state(m)[0], "building", "a branch is enough, whatever the pull requests say")

    def test_unknown_needs_leave_blocked_and_ready_apart(self):
        m = Mini()
        m.land("loop/base", 1)
        m.env_error["staging"] = "staging did not answer"
        m.concern("loop/base", concern_md())
        m.concern("loop/thing", concern_md(needs="[base]"))
        self.assertEqual(self.state(m)[0], "unknown")
        m.concern("loop/third", concern_md(questions=["| Q1 | Which? | C1 | This |"]))
        m.concern("loop/thing", concern_md(needs="[base, third]"))
        self.assertEqual(self.state(m)[0], "blocked", "one need known not to be done is enough")

    def test_needs_that_form_a_cycle_are_unknown(self):
        m = Mini()
        m.concern("loop/a", concern_md(needs="[b]"))
        m.concern("loop/b", concern_md(needs="[a]"))
        state, c = self.state(m, "loop/a")
        self.assertEqual(state, "unknown")
        self.assertIn("cycle", c["reason"])

    # Step 5: each loop's state.

    def test_loop_states(self):
        m = Mini()
        m.loop("parked", front="parked: D1", decisions=["| D1 | Wait for the review. | Ana, 2026-10-01 | |"])
        m.concern("parked/thing", concern_md())
        m.loop("empty")
        m.loop("planned", decisions=["| D1 | Planned. | Ana, 2026-10-01 | |"])
        m.concern("planned/thing", concern_md())
        m.concern("designed/thing", concern_md(decisions=["| D1 | Designed. | Ana, 2026-10-01 | |"]))
        m.land("finished/thing", 1)
        m.serve("staging")
        line = "- 2026-10-10 · C1 · HOLDS · rung 1 · staging @%s · ok" % m.main[:7]
        m.concern("finished/thing", concern_md(evidence=[line], shipped="Shipped."))
        m.loop("finished", goals=["- **G1** It all works. Prove: CI on main."], shipped="Shipped.")
        m.land("goal/thing", 2, files=("src/goal/a.py",))
        m.serve("staging")
        m.concern("goal/thing", concern_md(touches="[src/goal/]", shipped="Shipped.", evidence=[
            "- 2026-10-10 · C1 · HOLDS · rung 1 · staging @%s · ok" % m.main[:7]]))
        m.loop("goal", goals=["- **G1** A user can do it. Prove: 20 users, on production."])
        m.land("dark/thing", 3, files=("src/dark/a.py",))
        m.env_error["production"] = "production did not answer"
        m.concern("dark/thing", concern_md(ships_to="production", touches="[src/dark/]"))
        doc = self.derive(m)
        got = {l["id"]: l["state"] for l in doc["loops"]}
        self.assertEqual(got, {"dark": "unknown", "designed": "active", "empty": "open", "finished": "done",
                               "goal": "active", "parked": "parked", "planned": "backlog"})
        self.assertEqual(loop_of(doc, "empty")["next"], "/loop-design empty")
        self.assertIs(loop_of(doc, "finished")["goals"][0]["current_holds"], True)
        self.assertIs(loop_of(doc, "goal")["goals"][0]["current_holds"], False)
        self.assertFalse([s for s in doc["agents_can_start"] if s["concern"].startswith("parked/")],
                         "nothing starts in a parked loop")

    def test_a_backlog_loop_is_unknown_while_pull_requests_cannot_be_read(self):
        m = Mini()
        m.pr_error[PROJECT] = "gh: not authenticated"
        m.concern("planned/thing", concern_md())
        self.assertEqual(loop_of(self.derive(m), "planned")["state"], "unknown")

    # Step 6 and 7: the queue and what agents can start.

    def test_the_queue_counts_what_it_unblocks_through_needs_across_loops(self):
        m = Mini()
        m.concern("loop/base", concern_md(questions=["| Q1 | Which? | C1 | This |"]))
        m.concern("loop/middle", concern_md(needs="[base]"))
        m.concern("other/top", concern_md(needs="[loop/middle]"))
        m.concern("other/alone", concern_md(questions=["| Q1 | Where? | C1 | Here |"]))
        doc = self.derive(m)
        self.assertEqual([(i["id"], i["unblocks"]) for i in doc["queue"]], [
            ("loop/base/Q1", ["loop/base", "loop/middle", "other/top"]),
            ("other/alone/Q1", ["other/alone"])])
        self.assertEqual([i["gate"] for i in doc["queue"]], [None, None])

    def test_a_proof_item_needs_something_only_a_person_has(self):
        m = Mini()
        m.land("loop/thing", 1)
        m.serve("staging")
        sha = m.main[:7]
        m.concern("loop/thing", concern_md(evidence=[
            "- 2026-10-10 · C1 · UNPROVEN · rung 1 · staging @%s · needs a real phone, which only Ana has" % sha]))
        doc = self.derive(m)
        proof = [i for i in doc["queue"] if i["kind"] == "proof"]
        self.assertEqual(proof[0]["detail"]["missing"], "a real phone")
        self.assertEqual(proof[0]["detail"]["supplied_by"], "Ana")
        m.concern("loop/thing", concern_md(evidence=[
            "- 2026-10-10 · C1 · UNPROVEN · rung 1 · staging @%s · the load run timed out; rerun it" % sha]))
        doc = self.derive(m)
        self.assertFalse([i for i in doc["queue"] if i["kind"] == "proof"], "an agent can close this gap")
        self.assertEqual(doc["agents_can_start"], [
            {"concern": "loop/thing", "action": "prove", "command": "/loop-prove loop/thing staging"}])

    def test_a_refused_loop_document_pr_is_queued_with_the_checkers_lines(self):
        m = Mini()
        m.concern("loop/thing", concern_md())
        m.pr("docs/loop-record-2026-10-20", 7, "OPEN", body="Record.\n")
        m.checks.append({"repository": PROJECT, "number": 7, "head": m.main, "ok": False,
                         "failures": ["FAIL: changes a file outside docs/loops/: src/x/a.py"], "error": None})
        item = [i for i in self.derive(m)["queue"] if i["kind"] == "refused_pr"][0]
        self.assertEqual(item["loop"], "loop")
        self.assertEqual(item["detail"]["command"], "scripts/check_loop_pr.sh --pr 7")


class SkillTest(unittest.TestCase):
    """The script's states are the table's, and the skill runs the script while keeping the table as the
    specification."""

    @classmethod
    def setUpClass(cls):
        with open(SKILL, encoding="utf-8") as f:
            cls.skill = f.read()

    def test_the_script_has_exactly_the_tables_states(self):
        self.assertEqual(list(ls.CONCERN_STATES), derivation_table_states(self.skill) + ["unknown"])
        self.assertEqual(sorted(ls.LOOP_STATES), sorted(loop_states_in_step_5(self.skill) + ["unknown"]))

    def test_the_skill_runs_the_script(self):
        self.assertIn("[scripts/loop_status.py](scripts/loop_status.py)", self.skill)
        for words in ("gather", "derive --facts", "--json"):
            self.assertIn(words, self.skill)

    def test_the_table_has_the_rule_for_another_repository_and_a_loop_unknown(self):
        """command-center/D19 and D37."""
        self.assertRegex(self.skill, r"merged in another\s+repository")
        step_5 = re.search(r"^5\. \*\*Derive each loop's state\.\*\*(.*?)^\d+\. \*\*", self.skill, re.M | re.S).group(1)
        self.assertIn("unknown", step_5)
        self.assertIn("never guessed as active", step_5)


class CommandLineTest(unittest.TestCase):
    def run_script(self, *args, stdin=None):
        return subprocess.run([sys.executable, SCRIPT] + list(args), capture_output=True, text=True, input=stdin)

    def facts(self):
        m = Mini()
        m.land("loop/thing", 1)
        m.concern("loop/thing", concern_md())
        return m.facts()

    def test_derive_reads_a_facts_document(self):
        facts = self.facts()
        result = self.run_script("derive", "--facts", "-", "--json", stdin=json.dumps(facts))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ls.derive(facts))

    def test_a_facts_document_of_another_version_is_refused(self):
        facts = self.facts()
        facts["facts_version"] = ls.FACTS_VERSION + 1
        result = self.run_script("derive", "--facts", "-", stdin=json.dumps(facts))
        self.assertEqual(result.returncode, 2)
        self.assertIn("facts_version", result.stderr)

    def test_an_unknown_scope_is_refused(self):
        result = self.run_script("derive", "--facts", "-", "nowhere", stdin=json.dumps(self.facts()))
        self.assertEqual(result.returncode, 2)
        self.assertIn("nowhere", result.stderr)

    def test_gather_outside_a_repository_fails_cleanly(self):
        tmp = tempfile.mkdtemp(prefix="loop-status-empty-")
        try:
            result = subprocess.run([sys.executable, SCRIPT, "gather", "--repo", tmp], capture_output=True,
                                    text=True, env=dict(os.environ, GIT_CEILING_DIRECTORIES=os.path.dirname(tmp)))
            self.assertEqual(result.returncode, 2)
            self.assertIn("not a git repository", result.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
