#!/usr/bin/env python3
"""Derive where every loop and concern stands, from facts: the loop-status derivation as one script.

Usage:
    python3 loop_status.py [OPTIONS] [SCOPE]                gather the facts, derive, and print the board
    python3 loop_status.py gather [OPTIONS]                 print the facts document (JSON)
    python3 loop_status.py derive --facts FILE [OPTIONS] [SCOPE]
                                                            derive from a facts document (FILE, or - for stdin)

    --json          print the status document, which status.schema.json describes, instead of the board
    --repo DIR      the repository to read (default: the current directory)
    --project O/R   the project's key (default: from origin's URL, else from gh)
    --main BRANCH   the main branch (default: origin's default branch, else main)
    --as-of TIME    when the facts were gathered, as YYYY-MM-DDTHH:MM:SSZ (default: now, in UTC)
    --no-fetch      do not run git fetch first
    SCOPE           <loop> or <loop>/<concern>: what the board shows. The JSON always describes every loop.

Exit status: 0 when the board or the document was printed, whatever it says (an unknown is an answer, not an
error); 2 for a usage error, a facts document this script cannot read, or a repository it cannot gather from.

Gathering and deriving are separate (command-center/status-derivation C3). `gather` reads facts, read-only: the
loop documents and LOOP.md as they are on main (never the working tree), the main branch's head and its checks,
what each environment in LOOP.md §3 serves (by its served-commit command, only for rows agents may read), pull
requests (gh), branches, the commits on main that carry a Concern trailer, and the answers to the git questions
the derivation asks: whether a commit is an ancestor of another, what changed under some paths between two
commits, and where a branch started. `derive` is a pure function from such a facts document to the status
document. A caller that cannot run commands, such as a service that reads served commits over HTTP, supplies its
own facts document instead, and asks pending_queries(facts) which git questions it still has to answer.

The facts document (facts_version 1) is a JSON object:

    project, as_of                the project's key, and when the facts were gathered (UTC)
    files                         {path: text} for LOOP.md and every docs/loops/<loop>/<file>.md on main
    main                          {branch, sha, error}
    ci                            {commit, state, error}: the combined checks on main's head
    environments                  [{name, served, error}], LOOP.md §3's rows in order (main first if it has none)
    pull_requests                 [{repository, items, error}]; items as normalize_pr returns them
    branches                      {heads: {name: sha}, error}: origin's branches
    trailers, merges              {commits: [...], error}: commits on main with a Concern trailer ({sha,
                                  concerns}), and the merge commits on main's first-parent line ({sha, subject})
    repositories                  [{repository, default_branch, error}] for every other repository named
    loop_document_checks          [{repository, number, head, ok, failures, error}]: check_loop_pr.sh on each open
                                  loop-document pull request
    answers                       [{query, value, error}]: the git questions, answered
    log                           [{command, exit}]: what gather ran (only for people; derive never reads it)

A fact that could not be read carries its error, and whatever depends on it is unknown. Nothing is ever filled in
from a document.

The derivation table in loop-status's SKILL.md is the specification, and this script implements it row by row:
derive_concern() checks the rows from top to bottom and the first that matches wins, and derive_loop() is step 5.
If two runs on the same facts ever disagree, fix the table first, then this script.

Standard library only; Python 3.8 or later. Questions are read by questions.py, beside this file, so the format
has one reader. Each queue item is addressed by addressing.py, beside it too: the gate it crosses, the one person
it waits on, and who else sees it (command-center/addressed-to-people).
"""

import argparse
import datetime
import fnmatch
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FACTS_VERSION = 1
SCHEMA_VERSION = 1

_spec = importlib.util.spec_from_file_location("loop_status_questions", os.path.join(HERE, "questions.py"))
questions = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(questions)
_spec = importlib.util.spec_from_file_location("loop_status_addressing", os.path.join(HERE, "addressing.py"))
addressing = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(addressing)

# The rows of the derivation table, in its order, plus unknown; and step 5's loop states, plus unknown.
CONCERN_STATES = ("parked", "contradicted", "open", "blocked", "ready", "building", "merged", "shipped", "stale",
                  "done", "unknown")
LOOP_STATES = ("parked", "open", "backlog", "done", "active", "unknown")
# Step 6's kinds of queue item, then the Record step's, as the queue lists them among items that unblock as much.
QUEUE_ORDER = ("question", "review", "ship", "proof", "contradiction", "refused_pr", "record")

PR_FIELDS = "number,title,headRefName,baseRefName,state,isDraft,mergeCommit,body,url,statusCheckRollup,files"
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
FULL_SHA_RE = re.compile(r"\b[0-9a-f]{40}\b")
DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
AS_OF_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
FRONT_KEY_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):[ \t]*(.*?)\s*$")
ITEM_RE = re.compile(r"^- (~~)?\*\*([CG]\d+)\*\*:?[ \t]*(.*)$")
DECISION_ID_RE = re.compile(r"^(~~)?(D\d+)(~~)?$")
DECISION_NEED_RE = re.compile(r"^(?:([A-Za-z0-9][A-Za-z0-9._-]*)/)?(D\d+)$")
EVIDENCE_RE = re.compile(r"^- (\d{4}-\d{2}-\d{2}) · ([CGQ]\d+) · (HOLDS|CONTRADICTS|UNPROVEN) · rung (\d+) · "
                         r"(.+?) @([0-9a-f]{7,40}|\?) · (.+?)\s*$")
EVIDENCE_LIKE_RE = re.compile(r"^- \d{4}-\d{2}-\d{2} · [CG]\d+ · ")
ANY_EVIDENCE_RE = re.compile(r"^- \d{4}-\d{2}-\d{2} · ")
CONCERN_LINE_RE = re.compile(r"(?m)^Concern:[ \t]*(\S+)[ \t]*$")
MERGE_SUBJECT_RE = re.compile(r"^Merge pull request #(\d+) from (\S+)")
SQUASH_SUBJECT_RE = re.compile(r"\(#(\d+)\)$")
CONTRADICTS_REF_RE = re.compile(r"\bcontradicts ([A-Za-z0-9][A-Za-z0-9._-]*/D\d+)\b")
NEEDS_ONLY_RE = re.compile(r"^(?:it )?needs (?P<missing>.+?),? (?:which|that) only (?P<who>.+?) "
                           r"(?:can|could|has|have|holds?)\b", re.I)
ONLY_RE = re.compile(r"\bonly (?P<who>[^,;.]+?) (?:can|could|has|have|holds?)\b", re.I)
PROOF_HEADING_RE = re.compile(r"^#{2,3}\s+How it was proven", re.I)
PR_REF_RE = re.compile(r"^(?:([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+))?#?(\d+)$")
REPO_PATH_RE = re.compile(r"^([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?):(.+)$")


class FactsError(Exception):
    """A facts document this script cannot read, or a repository it cannot gather from."""


# --- Reading the loop documents ------------------------------------------------------------------------------------

def front_matter(text):
    """The `---` block at the top of a file, as {key: raw value}; {} when there is none."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}
    out = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return out
        m = FRONT_KEY_RE.match(line)
        if m:
            out[m.group(1)] = m.group(2)
    return {}


def unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def fm_list(fm, key):
    """A front matter list, `[a, b (c, d)]`, split at the commas outside brackets, parentheses and code."""
    raw = fm.get(key, "").strip()
    if not raw:
        return []
    if raw.startswith("[") and raw.endswith("]"):
        return [unquote(x) for x in questions.split_blocks(raw[1:-1].strip()) if unquote(x)]
    return [unquote(raw)]


def fm_scalar(fm, key):
    value = unquote(fm.get(key, ""))
    return value or None


def heading_name(text):
    """A section heading, lowercased, without its numbering: '3. Environments' is 'environments'."""
    return re.sub(r"^\d+(\.\d+)*\.?\s*", "", text.strip()).strip().lower()


def outline(text):
    """(title, {section: [lines]}): the first level-1 heading, and the body of each level-2 section, with HTML
    comments and the front matter removed, and headings inside fenced code ignored."""
    lines = questions.strip_comments(text).split("\n")
    start = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                start = i + 1
                break
    title, sections, current, fence = None, {}, None, False
    for line in lines[start:]:
        if FENCE_RE.match(line):
            fence = not fence
        m = None if fence else HEADING_RE.match(line)
        if m and len(m.group(1)) <= 2:
            if len(m.group(1)) == 1:
                title = title or m.group(2).strip()
                current = None
            else:
                current = heading_name(m.group(2))
                sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)
    return title, sections


def read_items(lines, letter):
    """The claims (C#) or goals (G#) in a section: [{id, text, struck}]."""
    items, current = [], None
    for line in lines:
        m = ITEM_RE.match(line)
        if m and m.group(2).startswith(letter):
            current = {"id": m.group(2), "struck": bool(m.group(1)), "parts": [m.group(3).strip()]}
            items.append(current)
        elif current is not None and line.startswith(" ") and line.strip():
            current["parts"].append(line.strip())
        else:
            current = None
    out = []
    for item in items:
        text = " ".join(p for p in item["parts"] if p)
        if item["struck"] and "~~" in text:
            text = text[:text.find("~~")].strip()
        out.append({"id": item["id"], "text": text or item["id"], "struck": item["struck"]})
    return out


def read_decisions(lines):
    """The rows of a Decisions table: [{id, struck, date, text, row}]."""
    rows = []
    for line in lines:
        if not line.strip().startswith("|") or questions.is_separator(line):
            continue
        cells = questions.split_row(line)
        m = DECISION_ID_RE.match(cells[0]) if cells else None
        if not m:
            continue
        text = cells[1] if len(cells) > 1 else ""
        dates = DATE_RE.findall(cells[2] if len(cells) > 2 else "") or DATE_RE.findall(" ".join(cells[1:]))
        rows.append({"id": m.group(2), "struck": bool(m.group(1)) or text.startswith("~~"),
                     "date": dates[0] if dates else None, "text": text.strip("~ ").strip() or m.group(2),
                     "row": " | ".join(cells)})
    return rows


def read_evidence(lines):
    """(lines, unreadable, any): the evidence lines about a C#, G# or Q#, the lines that look like one but do not
    read, and whether the section holds any evidence line at all (ship lines included)."""
    out, unreadable, any_line = [], [], False
    for line in lines:
        if ANY_EVIDENCE_RE.match(line):
            any_line = True
        m = EVIDENCE_RE.match(line)
        if m and 1 <= int(m.group(4)) <= 6:
            out.append({"date": m.group(1), "key": m.group(2), "verdict": m.group(3), "rung": int(m.group(4)),
                        "environment": m.group(5).strip(), "commit": None if m.group(6) == "?" else m.group(6),
                        "text": m.group(7)})
        elif EVIDENCE_LIKE_RE.match(line):
            unreadable.append(line.strip())
    return out, unreadable, any_line


def has_text(lines):
    return any(line.strip() for line in lines)


def tokens(entry):
    return [t for t in re.split(r"[\s,;()\[\]]+", entry.replace("`", " ")) if t]


def prove_clause(text):
    at = text.rfind("Prove:")
    return text[at + len("Prove:"):].strip() if at >= 0 else ""


def is_ci_claim(text):
    """Whether a claim's Prove says CI: it ends in CI, or CI on main, after any closing (per ...) note."""
    prove = prove_clause(text)
    while True:
        stripped = re.sub(r"\s*\([^()]*\)\s*[.;]?\s*$", "", prove)
        if stripped == prove:
            break
        prove = stripped
    prove = prove.rstrip(" .;")
    return bool(re.search(r"(?:^|[\s,])(?:in )?CI(?: on main)?$", prove))


def names_ci(text):
    """Whether a claim's Prove names CI anywhere, as "unit tests, in CI on main, then a run on staging" does. Such a
    claim holds on main while CI is green there, which is enough to meet a need (command-center/D50)."""
    return bool(re.search(r"(?<![\w-])CI(?![\w-])", prove_clause(text)))


def environment_rows(loop_md):
    """Every row of LOOP.md §3, in order: {name, readable, command, error}. A row whose served-commit command an
    agent may not run, or that has none, carries the error that makes it unknown."""
    if not loop_md:
        return []
    _, sections = outline(loop_md)
    body = next((lines for name, lines in sections.items() if name.endswith("environments")), None)
    if body is None:
        return []
    for i in range(len(body) - 1):
        if body[i].strip().startswith("|") and questions.is_separator(body[i + 1]):
            header = [c.lower() for c in questions.split_row(body[i])]
            table = body[i + 2:]
            break
    else:
        return []

    def column(start):
        return next((n for n, cell in enumerate(header) if cell.startswith(start)), None)

    name_at, read_at, served_at = column("environment"), column("agents may read"), column("served commit")
    rows = []
    for line in table:
        if not line.strip().startswith("|"):
            break
        cells = questions.split_row(line)

        def cell(at):
            return cells[at] if at is not None and at < len(cells) else ""

        name = cell(name_at).replace("`", "").replace("*", "").strip()
        if not name:
            continue
        readable = cell(read_at).lower().startswith("yes")
        served = cell(served_at)
        spans = re.findall(r"`([^`]+)`", served)
        command, error = None, None
        if not readable:
            error = "LOOP.md §3 says agents may not read %s" % name
        elif "TODO" in served:
            error = "LOOP.md §3 has no served-commit command for %s (TODO(owner))" % name
        elif not spans:
            error = "LOOP.md §3 has no served-commit command for %s" % name
        elif re.search(r"<[^<>\s]+>", spans[0]):
            error = "LOOP.md §3's served-commit command for %s has a placeholder: %s" % (name, spans[0])
        else:
            command = spans[0]
        rows.append({"name": name, "readable": readable, "command": command, "error": error})
    return rows


# --- Pull requests and checks --------------------------------------------------------------------------------------

def checks_state(rollup):
    """The combined state of a pull request's statusCheckRollup."""
    if rollup is None:
        return "unknown"
    if not rollup:
        return "none"
    seen = []
    for check in rollup:
        if "conclusion" not in check and "state" in check:
            state = (check.get("state") or "").upper()
            seen.append({"SUCCESS": "success", "FAILURE": "failure", "ERROR": "failure"}.get(state, "pending"))
            continue
        status = (check.get("status") or "COMPLETED").upper()
        conclusion = (check.get("conclusion") or "").upper()
        if status != "COMPLETED" or conclusion in ("", "PENDING"):
            seen.append("pending")
        elif conclusion in ("SUCCESS", "NEUTRAL", "SKIPPED"):
            seen.append("success")
        else:
            seen.append("failure")
    return "failure" if "failure" in seen else "pending" if "pending" in seen else "success"


def runs_state(runs):
    """The combined state of the workflow runs on a commit, as gh run list prints them."""
    if not runs:
        return "none"
    seen = []
    for run in runs:
        if (run.get("status") or "").lower() != "completed":
            seen.append("pending")
        elif (run.get("conclusion") or "").lower() in ("success", "neutral", "skipped"):
            seen.append("success")
        else:
            seen.append("failure")
    return "failure" if "failure" in seen else "pending" if "pending" in seen else "success"


def normalize_pr(raw, repository):
    """A pull request as gh pr list --json prints it, in the shape a facts document holds."""
    number = int(raw["number"])
    merge = raw.get("mergeCommit")
    merge = merge.get("oid") if isinstance(merge, dict) else None
    state = (raw.get("state") or "").lower()
    return {
        "repository": repository,
        "number": number,
        "url": raw.get("url") or "https://github.com/%s/pull/%d" % (repository, number),
        "title": raw.get("title") or "#%d" % number,
        "head": raw.get("headRefName") or "unknown",
        "base": raw.get("baseRefName") or "unknown",
        "state": state if state in ("open", "closed", "merged") else "closed",
        "draft": bool(raw.get("isDraft")),
        "merge_commit": merge.lower() if merge else None,
        "checks": checks_state(raw.get("statusCheckRollup")),
        "body": raw.get("body") or "",
        "files": [f["path"] for f in raw.get("files") or [] if isinstance(f, dict) and f.get("path")],
    }


def proof_section(body):
    """The body's 'How it was proven before the merge' section, without a closing Concern line; None if absent."""
    lines = body.replace("\r\n", "\n").split("\n")
    for i, line in enumerate(lines):
        if PROOF_HEADING_RE.match(line):
            level = len(line) - len(line.lstrip("#"))
            out = []
            for rest in lines[i + 1:]:
                m = re.match(r"^(#{1,6})\s", rest)
                if m and len(m.group(1)) <= level:
                    break
                out.append(rest)
            while out and (not out[-1].strip() or CONCERN_LINE_RE.match(out[-1].strip())):
                out.pop()
            text = "\n".join(out).strip()
            return text or None
    return None


def schema_pr(pr, on_main):
    return {"repository": pr["repository"], "number": pr["number"], "url": pr["url"], "title": pr["title"],
            "head": pr["head"], "base": pr["base"], "state": pr["state"], "draft": pr["draft"],
            "merge_commit": pr["merge_commit"], "on_main": on_main, "checks": pr["checks"]}


def pr_name(pr, project):
    return "#%d" % pr["number"] if pr["repository"] == project else "%s#%d" % (pr["repository"], pr["number"])


# --- Paths ---------------------------------------------------------------------------------------------------------

def path_matches(spec, path):
    """Whether path is under spec, the way git reads a pathspec: a prefix at a directory boundary, or a pattern."""
    if any(c in spec for c in "*?["):
        return fnmatch.fnmatchcase(path, spec)
    spec = spec.rstrip("/")
    return path == spec or path.startswith(spec + "/")


def paths_overlap(a, b):
    """The narrower of two touches when one contains the other, else None."""
    if any(c in a for c in "*?[") or any(c in b for c in "*?["):
        if fnmatch.fnmatchcase(b.rstrip("/"), a) or fnmatch.fnmatchcase(b, a):
            return b
        if fnmatch.fnmatchcase(a.rstrip("/"), b) or fnmatch.fnmatchcase(a, b):
            return a
        return None
    a0, b0 = a.rstrip("/"), b.rstrip("/")
    if a0 == b0 or b0.startswith(a0 + "/"):
        return b
    if a0.startswith(b0 + "/"):
        return a
    return None


# --- The git questions ---------------------------------------------------------------------------------------------

def query_key(query):
    return json.dumps(query, sort_keys=True)


def describe(query):
    kind = query["kind"]
    if kind == "ancestor":
        return "whether %s is an ancestor of %s in %s" % (query["commit"][:12], query["of"][:12], query["repository"])
    if kind == "changes":
        return "what changed under %s between %s and %s" % (", ".join(query["paths"]), query["from"][:12],
                                                             query["to"][:12])
    if kind == "merge_base":
        return "where %s and %s meet" % (query["a"][:12], query["b"][:12])
    return json.dumps(query)


class Oracle:
    """Answers the derivation's git questions from a facts document, and records the ones it has no answer for."""

    def __init__(self, facts):
        self.answers = {}
        for answer in facts.get("answers") or []:
            if isinstance(answer, dict) and isinstance(answer.get("query"), dict):
                self.answers[query_key(answer["query"])] = answer
        self.pending, self._pending = [], set()

    def ask(self, query):
        """(value, error). A value of None is unknown, and the error says why."""
        key = query_key(query)
        answer = self.answers.get(key)
        if answer is None:
            if key not in self._pending:
                self._pending.add(key)
                self.pending.append(query)
            return None, "not gathered: %s" % describe(query)
        if answer.get("error") or answer.get("value") is None:
            return None, answer.get("error") or "no answer: %s" % describe(query)
        return answer["value"], None


# --- The model -----------------------------------------------------------------------------------------------------

class Loop:
    def __init__(self, loop_id, text):
        self.id = loop_id
        self.path = "docs/loops/%s/README.md" % loop_id
        self.exists = text is not None
        text = text or ""
        fm = front_matter(text)
        title, sections = outline(text)
        self.title = title or loop_id
        self.parked = fm_scalar(fm, "parked")
        self.owner = fm_scalar(fm, "owner")
        self.members = fm_list(fm, "members")
        self.goals = read_items(sections.get("goals", []), "G")
        self.decisions = read_decisions(sections.get("shared decisions", []))
        self.evidence, self.unreadable, _ = read_evidence(sections.get("evidence", []))
        self.shipped_note = has_text(sections.get("shipped", []))
        parsed = questions.parse(text, source=self.path, ref_prefix=loop_id) if text else {"questions": [],
                                                                                              "problems": []}
        self.questions, self.problems = parsed["questions"], parsed["problems"]
        self.concerns = []
        self.state = self.reason = self.next = None


class Concern:
    def __init__(self, loop, concern_id, text, project):
        self.loop = loop
        self.id = concern_id
        self.ref = "%s/%s" % (loop.id, concern_id)
        self.path = "docs/loops/%s/%s.md" % (loop.id, concern_id)
        fm = front_matter(text)
        title, sections = outline(text)
        self.title = title or concern_id
        self.needs = fm_list(fm, "needs")
        self.touches = fm_list(fm, "touches")
        self.effects = fm_list(fm, "effects")
        self.ships_to = fm_scalar(fm, "ships-to")
        self.pr_entries = fm_list(fm, "prs")
        self.parked = fm_scalar(fm, "parked")
        self.claims = read_items(sections.get("done when", []), "C")
        self.decisions = read_decisions(sections.get("decisions", []))
        self.evidence, self.unreadable, self.any_evidence = read_evidence(sections.get("evidence", []))
        self.shipped_note = has_text(sections.get("shipped", []))
        parsed = questions.parse(text, source=self.path, ref_prefix=self.ref)
        self.questions, self.problems = parsed["questions"], parsed["problems"]
        # Touches, as (repository, path).
        self.touch_paths = []
        for entry in self.touches:
            m = REPO_PATH_RE.match(entry)
            if m:
                repo = m.group(1) if "/" in m.group(1) else "%s/%s" % (project.split("/")[0], m.group(1))
                self.touch_paths.append((repo, m.group(2)))
            else:
                self.touch_paths.append((project, entry))
        # Pull requests listed in prs, as (repository, number).
        self.pr_refs = []
        for entry in self.pr_entries:
            m = PR_REF_RE.match(entry.strip())
            if m:
                self.pr_refs.append((m.group(1) or project, int(m.group(2))))
        # Linked work, filled in by the project.
        self.prs = []
        self.unread_prs = []
        self.commits = []
        self.merges = []
        self.branch_exists = None
        self.branch_head = None
        # Derived.
        self.state = self.reason = self.next = None
        self.missing = []
        self.contradictions = []
        self.prove_needs = []
        self.open_by_contract = False
        self.claim_results = {}
        self.serves = self.served = None

    def live_claims(self):
        return [c for c in self.claims if not c["struck"]]

    def lines(self, key):
        return [line for line in self.evidence if line["key"] == key]

    def local_touches(self, project):
        return [p for repo, p in self.touch_paths if repo == project]


class Project:
    """The loop documents of one project, and the work linked to each concern."""

    def __init__(self, facts):
        if not isinstance(facts, dict):
            raise FactsError("a facts document is a JSON object")
        if facts.get("facts_version") != FACTS_VERSION:
            raise FactsError("facts_version is %r; this script reads %d" % (facts.get("facts_version"), FACTS_VERSION))
        self.facts = facts
        self.project = facts.get("project") or "unknown"
        self.oracle = Oracle(facts)
        main = facts.get("main") or {}
        self.main_branch = main.get("branch") or "main"
        self.main = (main.get("sha") or "").lower()
        if not SHA_RE.match(self.main):
            raise FactsError("the facts have no main branch head: %s" % (main.get("error") or "main.sha is missing"))
        self.files = facts.get("files") or {}
        self.loop_md = self.files.get("LOOP.md")
        ci = facts.get("ci") or {}
        self.ci = ci.get("state") if ci.get("state") in ("success", "failure", "pending", "none") else "unknown"
        self.ci_error = ci.get("error") or ("the checks on main were not gathered" if self.ci == "unknown" else None)
        self.environments = []
        for env in facts.get("environments") or []:
            served = (env.get("served") or "").lower() or None
            if served and not SHA_RE.match(served):
                served = None
            error = env.get("error") or (None if served else "no served commit was gathered")
            self.environments.append({"name": env["name"], "served": None if error else served, "error": error})
        if not any(e["name"] == "main" for e in self.environments):
            self.environments.insert(0, {"name": "main", "served": self.main, "error": None})
        self.read_loops()
        self.link_work()

    # Reading.

    def read_loops(self):
        texts = {}
        for path, text in self.files.items():
            m = re.match(r"^docs/loops/([^/]+)/([^/]+)\.md$", path)
            if m and ID_RE.match(m.group(1)) and (m.group(2) == "README" or ID_RE.match(m.group(2))):
                texts.setdefault(m.group(1), {})[m.group(2)] = text
        self.loops = []
        self.by_ref = {}
        for loop_id in sorted(texts):
            loop = Loop(loop_id, texts[loop_id].get("README"))
            for concern_id in sorted(n for n in texts[loop_id] if n != "README"):
                c = Concern(loop, concern_id, texts[loop_id][concern_id], self.project)
                loop.concerns.append(c)
                self.by_ref[c.ref] = c
            self.loops.append(loop)
        self.loop_by_id = {loop.id: loop for loop in self.loops}

    def concerns(self):
        return [c for loop in self.loops for c in loop.concerns]

    def other_repositories(self):
        """Every other repository named in a touches or prs entry."""
        names = set()
        for c in self.concerns():
            names.update(repo for repo, _ in c.touch_paths)
            names.update(repo for repo, _ in c.pr_refs)
        names.discard(self.project)
        return sorted(names)

    def resolve_need(self, c, need):
        """('decision', loop, D#), ('concern', ref) or ('missing', text) for one entry of needs."""
        m = DECISION_NEED_RE.match(need)
        if m:
            return ("decision", m.group(1) or c.loop.id, m.group(2))
        ref = need if "/" in need else "%s/%s" % (c.loop.id, need)
        return ("concern", ref) if ref in self.by_ref else ("missing", ref)

    def shared_decision(self, loop_id, number):
        loop = self.loop_by_id.get(loop_id)
        if loop is None:
            return None
        return next((d for d in loop.decisions if d["id"] == number), None)

    def environment(self, name):
        return next((e for e in self.environments if e["name"] == name), None)

    # Linking work to concerns (step 3).

    def link_work(self):
        self.pr_facts = {}
        for entry in self.facts.get("pull_requests") or []:
            self.pr_facts[entry["repository"]] = entry
        self.repositories = {r["repository"]: r for r in self.facts.get("repositories") or []}
        self.on_main = {}
        for repo, entry in sorted(self.pr_facts.items()):
            for pr in entry.get("items") or []:
                refs = set()
                if pr["head"] in self.by_ref:
                    refs.add(pr["head"])
                refs.update(r for r in CONCERN_LINE_RE.findall(pr.get("body") or "") if r in self.by_ref)
                for c in self.concerns():
                    if (repo, pr["number"]) in c.pr_refs:
                        refs.add(c.ref)
                for ref in sorted(refs):
                    self.by_ref[ref].prs.append(pr)
        for c in self.concerns():
            c.prs.sort(key=lambda p: (p["repository"] != self.project, p["repository"], p["number"]))
            for repo, number in c.pr_refs:
                entry = self.pr_facts.get(repo)
                if entry and not entry.get("error") and not any(
                        p["repository"] == repo and p["number"] == number for p in c.prs):
                    c.unread_prs.append("%s#%d" % (repo, number))
        trailers = self.facts.get("trailers") or {}
        for commit in trailers.get("commits") or []:
            for ref in commit.get("concerns") or []:
                if ref in self.by_ref and commit["sha"] not in self.by_ref[ref].commits:
                    self.by_ref[ref].commits.append(commit["sha"])
        if self.prs_missing(self.project):
            merges = self.facts.get("merges") or {}
            for commit in merges.get("commits") or []:
                m = MERGE_SUBJECT_RE.match(commit.get("subject") or "")
                if m:
                    branch = m.group(2).split("/", 1)[1] if "/" in m.group(2) else m.group(2)
                    if branch in self.by_ref:
                        self.by_ref[branch].merges.append(commit["sha"])
        branches = self.facts.get("branches") or {}
        heads = None if branches.get("error") or branches.get("heads") is None else branches["heads"]
        for c in self.concerns():
            if heads is not None:
                c.branch_exists = c.ref in heads
                c.branch_head = heads.get(c.ref)

    def prs_missing(self, repository):
        entry = self.pr_facts.get(repository)
        if entry is None:
            return "the pull requests of %s were not gathered" % repository
        return entry.get("error")

    def pr_on_main(self, pr):
        """(value, error): whether a pull request's merge commit is on its repository's main."""
        key = (pr["repository"], pr["number"])
        if key not in self.on_main:
            if pr["state"] != "merged" or not pr["merge_commit"]:
                self.on_main[key] = (None, None)
            elif pr["repository"] == self.project:
                self.on_main[key] = self.oracle.ask({"kind": "ancestor", "repository": self.project,
                                                     "commit": pr["merge_commit"], "of": self.main})
            else:
                repo = self.repositories.get(pr["repository"]) or {}
                if repo.get("error") or not repo.get("default_branch"):
                    self.on_main[key] = (None, "%s's default branch: %s" % (
                        pr["repository"], repo.get("error") or "not gathered"))
                else:
                    self.on_main[key] = self.oracle.ask({"kind": "ancestor", "repository": pr["repository"],
                                                         "commit": pr["merge_commit"], "of": repo["default_branch"]})
        return self.on_main[key]


# --- Three-valued facts about a concern's work ---------------------------------------------------------------------

def any3(values):
    """True if any is True, None if none is True but one is unknown, else False."""
    values = list(values)
    if any(v is True for v in values):
        return True
    return None if any(v is None for v in values) else False


class Derivation:
    def __init__(self, facts):
        self.p = Project(facts)
        self.oracle = self.p.oracle
        self.book = addressing.Book(self.p.loop_md, [
            {"id": loop.id, "path": loop.path, "owner": loop.owner, "members": loop.members,
             "parked": bool(loop.parked)} for loop in self.p.loops])
        self.cycles = self.find_cycles()
        self.blocked_by = self.question_blocks()

    # Facts about work.

    def repos_of(self, c):
        return sorted({self.p.project} | {r for r, _ in c.pr_refs})

    def prs_unreadable(self, c):
        """Why some pull request that may link c cannot be read, or None."""
        reasons = []
        for repo in self.repos_of(c):
            error = self.p.prs_missing(repo)
            if error:
                reasons.append(("pull requests" if repo == self.p.project else "pull requests in %s" % repo, error))
        reasons += [("pull request %s" % ref, "not in the pull requests read") for ref in c.unread_prs]
        return reasons

    def counted_prs(self, c):
        """Open or merged pull requests: what counts as work. One closed without merging was abandoned."""
        return [p for p in c.prs if p["state"] in ("open", "merged")]

    def built(self, c):
        """True when c has linked work (a pull request open or merged, its branch, a commit with its trailer)."""
        known = bool(self.counted_prs(c)) or c.branch_exists is True or bool(c.commits) or bool(c.merges)
        if known:
            return True
        if c.branch_exists is None or self.prs_unreadable(c):
            return None
        return False

    def open_or_branch(self, c):
        if any(p["state"] == "open" for p in c.prs) or c.branch_exists is True:
            return True
        if c.branch_exists is None or self.prs_unreadable(c):
            return None
        return False

    def work_on_main(self, c):
        """(value, why): whether any of c's work is on main. Without the project's pull requests, git alone says:
        trailers and merge-commit subjects (step 3)."""
        if c.commits or c.merges:
            return True, None
        values, errors = [], []
        for pr in c.prs:
            if pr["state"] == "merged":
                value, error = self.p.pr_on_main(pr)
                values.append(value)
                if error:
                    errors.append(error)
        if any(v is True for v in values):
            return True, None
        unreadable = [(f, e) for f, e in self.prs_unreadable(c) if f != "pull requests"]
        if any(v is None for v in values) or unreadable:
            return None, "; ".join(errors + ["%s: %s" % fe for fe in unreadable])
        return False, None

    def merge_commits(self, c):
        """The local commits that must be served (merge commits of PRs on main, and trailer commits), the other
        repositories' merged PRs on their main, and whether some merged PR's place is unknown."""
        local, foreign, unknown = [], [], False
        for pr in c.prs:
            if pr["state"] != "merged":
                continue
            value, _ = self.p.pr_on_main(pr)
            if value is None:
                unknown = True
            elif value:
                (local if pr["repository"] == self.p.project else foreign).append(pr)
        commits = [pr["merge_commit"] for pr in local] + c.commits + c.merges
        seen = []
        for sha in commits:
            if sha not in seen:
                seen.append(sha)
        return seen, foreign, unknown

    def serves(self, c):
        """(environment, served commit, error, serves) for c's ships-to, per the table's definition of serves."""
        if c.serves is not None or c.served is not None:
            return c.served
        if not c.ships_to:
            c.served = (None, None, "the contract has no ships-to", None)
            return c.served
        on_main, _ = self.work_on_main(c)
        if c.ships_to == "main":
            # The main branch's head serves whatever is on main; for a PR merged in another repository, that
            # repository's main does (command-center/D19).
            c.served = ("main", self.p.main, None, on_main)
            return c.served
        env = self.p.environment(c.ships_to)
        if env is None:
            c.served = (c.ships_to, None, "LOOP.md §3 has no row named %s" % c.ships_to, None)
            return c.served
        if env["error"]:
            c.served = (c.ships_to, None, env["error"], None)
            return c.served
        commits, foreign, unknown = self.merge_commits(c)
        if not commits and not foreign:
            c.served = (c.ships_to, env["served"], None, None if (unknown or on_main is None) else False)
            return c.served
        values = [self.oracle.ask({"kind": "ancestor", "repository": self.p.project, "commit": sha,
                                   "of": env["served"]})[0] for sha in commits]
        if any(v is False for v in values):
            result = False
        elif foreign or unknown or any(v is None for v in values):
            result = None
        else:
            result = True
        c.served = (c.ships_to, env["served"], None, result)
        return c.served

    def serves_errors(self, c):
        """Why c's serving cannot be read, as missing facts."""
        env, _, error, value = self.serves(c)
        out = []
        if error and c.ships_to:
            out.append("%s's served commit: %s" % (c.ships_to, error))
        if value is None and not error:
            commits, foreign, unknown = self.merge_commits(c)
            if foreign:
                out.append("whether %s serves %s: command-center/D19 covers a pull request merged in another "
                           "repository only for ships-to: main" % (env, ", ".join(
                               pr_name(p, self.p.project) for p in foreign)))
            on_main, why = self.work_on_main(c)
            if unknown or on_main is None:
                out.append("whether its work is on main: %s" % (why or "a merged pull request's place is unknown"))
            for sha in commits:
                value, err = self.oracle.ask({"kind": "ancestor", "repository": self.p.project, "commit": sha,
                                              "of": self.serves(c)[1]})
                if value is None:
                    out.append("whether %s serves %s: %s" % (env, sha[:7], err))
        return out

    # Claims.

    def needed_decisions_superseded(self, c):
        out = []
        for need in c.needs:
            kind = self.p.resolve_need(c, need)
            if kind[0] == "decision":
                d = self.p.shared_decision(kind[1], kind[2])
                if d is not None and d["struck"]:
                    out.append("%s/%s" % (kind[1], kind[2]))
        return out

    def claim_result(self, c, claim):
        """('current' | 'stale' | 'missing' | 'unknown', why) for one claim on c's ships-to, which serves its work."""
        key = claim["id"]
        if key in c.claim_results:
            return c.claim_results[key]
        env, served, _, _ = self.serves(c)
        main7 = self.p.main[:7]
        if is_ci_claim(claim["text"]):
            if self.p.ci == "success":
                result = ("current", "%s holds by CI, which is green on %s" % (key, main7))
            elif self.p.ci == "unknown":
                result = ("unknown", "%s holds by CI, and the checks on main @%s cannot be read: %s" % (
                    key, main7, self.p.ci_error))
            else:
                result = ("missing", "%s holds by CI, which is %s on main @%s" % (key, self.p.ci, main7))
            c.claim_results[key] = result
            return result
        lines = c.lines(key)
        if not lines:
            result = ("missing", "%s has no evidence" % key)
        else:
            last = lines[-1]
            if last["verdict"] != "HOLDS":
                result = ("missing", "%s's latest verdict is %s" % (key, last["verdict"]))
            elif last["environment"] != env:
                result = ("missing", "%s's latest HOLDS is on %s, not %s" % (key, last["environment"], env))
            elif last["commit"] is None:
                result = ("missing", "%s's latest HOLDS was migrated without a commit (@?), which never counts" % key)
            else:
                result = self.holds_since(c, key, last, served, env)
        c.claim_results[key] = result
        return result

    def holds_since(self, c, key, line, served, env):
        proof = line["commit"]
        value, error = self.oracle.ask({"kind": "ancestor", "repository": self.p.project, "commit": proof,
                                        "of": served})
        if value is None:
            return ("unknown", "whether %s's HOLDS @%s is in what %s serves cannot be read: %s" % (
                key, proof, env, error))
        if not value:
            return ("missing", "%s's HOLDS cites %s, which %s @%s does not include" % (key, proof, env, served[:7]))
        paths = c.local_touches(self.p.project)
        foreign = [(r, p) for r, p in c.touch_paths if r != self.p.project]
        if paths:
            changed, error = self.oracle.ask({"kind": "changes", "repository": self.p.project, "from": proof,
                                              "to": served, "paths": paths})
            if changed is None:
                return ("unknown", "what changed under its touches since %s cannot be read: %s" % (proof, error))
            if changed:
                return ("stale", "%s had a current HOLDS on %s @%s, but %s changed since, in %s" % (
                    key, env, proof, ", ".join(paths), ", ".join(s[:7] for s in changed)))
        if foreign:
            return ("unknown", "changes under %s since %s cannot be read from this repository" % (
                ", ".join("%s:%s" % rp for rp in foreign), proof))
        superseded = self.needed_decisions_superseded(c)
        if superseded:
            return ("stale", "%s had a current HOLDS on %s @%s, but %s, which it needs, has been superseded" % (
                key, env, proof, ", ".join(superseded)))
        return ("current", "%s HOLDS rung %d on %s @%s" % (key, line["rung"], env, proof))

    def current_holds(self, c, claim):
        if claim["struck"] or not c.ships_to:
            return None
        _, _, _, serves = self.serves(c)
        if serves is None:
            return None
        if serves is False:
            return False
        result = self.claim_result(c, claim)[0]
        return True if result == "current" else None if result == "unknown" else False

    # Needs (command-center/D50): a need is met once its work is on main and every claim holds on some environment.

    def need_met(self, other):
        """Whether a concern in some needs is met: {met: True | False | None, detail, missing, prove}. detail
        completes "<need>, which it needs, ...", missing names the facts an unknown rests on, and prove is the
        command that would prove one of its unproven claims, when its work is on main."""
        out = {"met": None, "detail": None, "missing": [], "prove": None}
        if other.state is None:
            out["missing"] = ["the state of %s" % other.ref]
            return out
        if other.state == "done":
            return dict(out, met=True, detail="is done")
        if other.state == "contradicted":
            # A contradiction is a reason to stop, wherever it was seen.
            return dict(out, met=False, detail="is contradicted")
        on_main, why = self.work_on_main(other)
        if on_main is None:
            return dict(out, missing=["whether the work of %s, which it needs, is on main: %s" % (other.ref, why)])
        if on_main is False:
            return dict(out, met=False, detail="is %s, and its work is not on main" % other.state)
        results = [self.claim_proven(other, claim) for claim in other.live_claims()]
        unproven = [why for result, why in results if result == "missing"]
        if unproven:
            env = self.prove_environment(other)
            return dict(out, met=False, detail="is %s, and not yet proven on any environment: %s" % (
                other.state, "; ".join(unproven)), prove="/loop-prove %s %s" % (other.ref, env) if env else None)
        unknown = [why for result, why in results if result == "unknown"]
        if unknown:
            return dict(out, missing=unknown)
        proven = "; ".join(why for _, why in results) or "it has no claims"
        return dict(out, met=True, detail="is proven: %s" % proven)

    def claim_proven(self, c, claim):
        """('holds' | 'missing' | 'unknown', why): whether a claim holds on some environment of LOOP.md §3, at a
        commit on main with nothing under c's touches changed since, or by CI on main while CI is green there."""
        key = claim["id"]
        main7 = self.p.main[:7]
        failed, unknown = [], []
        if names_ci(claim["text"]):
            if self.p.ci == "success":
                return ("holds", "%s holds by CI, which is green on %s" % (key, main7))
            if self.p.ci == "unknown":
                unknown.append("%s holds by CI, and the checks on main @%s cannot be read: %s" % (
                    key, main7, self.p.ci_error))
            else:
                failed.append("%s holds by CI, which is %s on main @%s" % (key, self.p.ci, main7))
        latest = {}
        for line in c.lines(key):
            latest[line["environment"]] = line
        for env, line in latest.items():
            if line["verdict"] != "HOLDS":
                failed.append("%s's latest line on %s is %s" % (key, env, line["verdict"]))
            elif self.p.environment(env) is None:
                failed.append("%s holds only on %s, and %s is not a row of LOOP.md §3" % (key, env, env))
            elif line["commit"] is None:
                failed.append("%s's HOLDS on %s was migrated without a commit (@?), which never counts" % (key, env))
            else:
                result, why = self.proven_since(c, key, line)
                if result == "holds":
                    return (result, why)
                (unknown if result == "unknown" else failed).append(why)
        if unknown:
            return ("unknown", "; ".join(unknown))
        return ("missing", "; ".join(failed) or "%s has no evidence" % key)

    def proven_since(self, c, key, line):
        """claim_proven for one HOLDS line: its commit is on main, and nothing under touches changed since."""
        proof, env = line["commit"], line["environment"]
        value, error = self.oracle.ask({"kind": "ancestor", "repository": self.p.project, "commit": proof,
                                        "of": self.p.main})
        if value is None:
            return ("unknown", "whether %s's HOLDS on %s @%s is on main cannot be read: %s" % (key, env, proof, error))
        if not value:
            return ("missing", "%s's HOLDS on %s cites %s, which is not on main" % (key, env, proof))
        paths = c.local_touches(self.p.project)
        if paths:
            changed, error = self.oracle.ask({"kind": "changes", "repository": self.p.project, "from": proof,
                                              "to": self.p.main, "paths": paths})
            if changed is None:
                return ("unknown", "what changed under the touches of %s since %s cannot be read: %s" % (
                    c.ref, proof, error))
            if changed:
                return ("missing", "%s held on %s @%s, but %s changed since, in %s" % (
                    key, env, proof, ", ".join(paths), ", ".join(s[:7] for s in changed)))
        foreign = [(r, p) for r, p in c.touch_paths if r != self.p.project]
        if foreign:
            return ("unknown", "changes under %s since %s cannot be read from this repository" % (
                ", ".join("%s:%s" % rp for rp in foreign), proof))
        superseded = self.needed_decisions_superseded(c)
        if superseded:
            return ("missing", "%s held on %s @%s, but %s, which %s needs, has been superseded" % (
                key, env, proof, ", ".join(superseded), c.id))
        return ("holds", "%s HOLDS rung %d on %s @%s" % (key, line["rung"], env, proof))

    def own_rows(self, c):
        """The rows of LOOP.md §3 that run c's code, lowest first: main for ships-to: main, otherwise every row
        but main, listed no higher than ships-to, with the same part after the / (command-center/needs-proven D1).
        Rows built from one repository serve every concern on main by ancestry, so serving alone is not enough."""
        if c.ships_to == "main":
            return [e for e in self.p.environments if e["name"] == "main"]
        names = [e["name"] for e in self.p.environments]
        if not c.ships_to or c.ships_to not in names:
            return []
        service = c.ships_to.partition("/")[2]
        return [e for e in self.p.environments[:names.index(c.ships_to) + 1]
                if e["name"] != "main" and e["name"].partition("/")[2] == service]

    def prove_environment(self, c):
        """Where to prove c's unproven claims: the lowest of its own rows that serves its work, or None when none
        does, so that what needs it waits on its own next step (command-center/needs-proven D2)."""
        if c.ships_to == "main":
            return "main"
        commits, _, _ = self.merge_commits(c)
        if not commits:
            return None
        for env in self.own_rows(c):
            if env["error"] or not env["served"]:
                continue
            values = [self.oracle.ask({"kind": "ancestor", "repository": self.p.project, "commit": sha,
                                       "of": env["served"]})[0] for sha in commits]
            if all(v is True for v in values):
                return env["name"]
        return None

    def find_cycles(self):
        graph = {}
        for c in self.p.concerns():
            graph[c.ref] = [k[1] for k in (self.p.resolve_need(c, n) for n in c.needs) if k[0] == "concern"]
        index, low, stack, on_stack, cycles, counter = {}, {}, [], set(), {}, [0]

        def visit(v):
            index[v] = low[v] = counter[0]
            counter[0] += 1
            stack.append(v)
            on_stack.add(v)
            for w in graph[v]:
                if w not in index:
                    visit(w)
                    low[v] = min(low[v], low[w])
                elif w in on_stack:
                    low[v] = min(low[v], index[w])
            if low[v] == index[v]:
                component = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    component.append(w)
                    if w == v:
                        break
                if len(component) > 1 or v in graph[v]:
                    for w in component:
                        cycles[w] = sorted(component)

        for v in sorted(graph):
            if v not in index:
                visit(v)
        return cycles

    def question_blocks(self):
        """{concern ref: [question refs]}: the unanswered questions that block one of its claims."""
        out = {}
        for loop in self.p.loops:
            for q in loop.questions:
                if not q["open"]:
                    continue
                for entry in q["blocks"]:
                    for t in tokens(entry):
                        ref = t if "/" in t else "%s/%s" % (loop.id, t)
                        if ref in self.p.by_ref:
                            out.setdefault(ref, []).append(q)
            for c in loop.concerns:
                for q in c.questions:
                    if not q["open"]:
                        continue
                    for entry in q["blocks"]:
                        for t in tokens(entry):
                            if re.match(r"^C\d+$", t) or t == c.id:
                                target = c.ref
                            elif t in self.p.by_ref and "/" in t:
                                target = t
                            else:
                                continue
                            if q not in out.setdefault(target, []):
                                out[target].append(q)
        return out

    # The table (step 4).

    def derive_concern(self, c, chain=()):
        if c.state is not None:
            return
        if c.ref in chain:
            return
        self.rows(c, chain + (c.ref,))
        if c.state == "unknown" and not c.missing:
            c.missing = ["a fact the table needs: %s" % c.reason]

    def set(self, c, state, reason, next_step, missing=()):
        c.state, c.reason, c.next = state, reason, next_step
        c.missing = list(dict.fromkeys(list(missing)))

    def rows(self, c, chain):
        ref = c.ref
        # parked
        if c.parked:
            d = next((x for x in c.decisions if x["id"] == c.parked), None)
            why = d["text"] if d else "%s is not in its Decisions" % c.parked
            return self.set(c, "parked", "Front matter has parked: %s" % c.parked,
                            "Nothing until %s's condition holds: %s" % (c.parked, why))
        # contradicted
        for claim in c.live_claims():
            lines = c.lines(claim["id"])
            if lines and lines[-1]["verdict"] == "CONTRADICTS":
                line = lines[-1]
                later = [d for d in c.decisions if d["date"] and d["date"] > line["date"]]
                named = re.compile(r"`%s`|(?<![\w-])%s(?![\w-])" % (re.escape(c.id), re.escape(c.ref)))
                later += [d for d in c.loop.decisions if d["date"] and d["date"] > line["date"] and named.search(d["row"])]
                if not later:
                    c.contradictions.append((claim, line))
        if c.contradictions:
            claim, line = c.contradictions[0]
            return self.set(c, "contradicted", "%s's latest verdict is CONTRADICTS (%s, %s, rung %d: %s), and no "
                            "decision is dated after it" % (claim["id"], line["date"], line["environment"],
                                                            line["rung"], line["text"]),
                            "/loop-design %s" % ref)
        # open
        blocking = self.blocked_by.get(ref, [])
        if blocking:
            return self.set(c, "open", "; ".join("%s (%s) blocks %s and is unanswered" % (
                q["ref"], q["question"], ", ".join(q["blocks"]) or c.id) for q in blocking), "/loop-design %s" % ref)
        gaps = []
        for need in c.needs:
            kind = self.p.resolve_need(c, need)
            if kind[0] == "decision":
                d = self.p.shared_decision(kind[1], kind[2])
                if d is None:
                    gaps.append("it needs %s/%s, which its loop does not record" % (kind[1], kind[2]))
                elif d["struck"]:
                    gaps.append("it needs %s/%s, which has been superseded" % (kind[1], kind[2]))
        lacks = [name for name, missing in (("Done when", not c.live_claims()), ("touches", not c.touches),
                                            ("ships-to", not c.ships_to)) if missing]
        if lacks:
            gaps.insert(0, "the contract lacks %s" % " and ".join(lacks))
        built = self.built(c)
        if gaps:
            if built is False:
                c.open_by_contract = True
                return self.set(c, "open", "Nothing is built yet, and %s" % "; ".join(gaps), "/loop-design %s" % ref)
            if built is None:
                return self.set(c, "unknown", "%s, so it is open unless something is built, and whether anything "
                                "is built cannot be read" % "; ".join(gaps).capitalize(), self.fix_next(c),
                                self.unread_missing(c))
        # blocked, ready
        if built is not True:
            not_met, unknown, missing, met = [], [], [], []
            for need in c.needs:
                kind = self.p.resolve_need(c, need)
                if kind[0] == "decision":
                    continue
                if kind[0] == "missing":
                    not_met.append((kind[1], None, "does not exist", None))
                    continue
                other = self.p.by_ref[kind[1]]
                if ref in self.cycles and other.ref in self.cycles.get(ref, []):
                    unknown.append(other.ref)
                    missing.append("its needs form a cycle: %s" % ", ".join(self.cycles[ref]))
                    continue
                self.derive_concern(other, chain)
                need = self.need_met(other)
                if need["met"] is True:
                    met.append("%s, which it needs, %s" % (other.ref, need["detail"]))
                elif need["met"] is None:
                    unknown.append(other.ref)
                    missing += need["missing"] or other.missing or ["the state of %s" % other.ref]
                else:
                    not_met.append((other.ref, other, need["detail"], need["prove"]))
            if built is False:
                if not_met:
                    c.prove_needs = [{"concern": n, "command": p} for n, _, _, p in not_met if p]
                    name, other, detail, prove = not_met[0]
                    next_step = prove or (other.next if other is not None and other.next else "/loop-design %s" % ref)
                    return self.set(c, "blocked", "Nothing is built yet, and %s" % "; ".join(
                        "%s, which it needs, %s" % (n, d) for n, _, d, _ in not_met), next_step)
                if unknown:
                    cycle = ref in self.cycles
                    return self.set(c, "unknown", "Nothing is built yet, but %s" % (
                        "its needs form a cycle (%s), so whether they are met cannot be read" % ", ".join(
                            self.cycles[ref]) if cycle else "whether %s, which it needs, is met cannot be read"
                        % ", ".join(unknown)), self.fix_next(c), missing)
                return self.set(c, "ready", "Nothing is built yet: no linked pull request, no %s branch, no commit "
                                "with its trailer%s" % (ref, "".join("; %s" % m for m in met)), "/loop-build %s" % ref)
            # built is None: ready or blocked cannot be told from building.
            what = "blocked" if not_met else "ready"
            return self.set(c, "unknown", "No %s branch and no commit with its trailer, but whether a pull request "
                            "links it cannot be read, so %s and building cannot be told apart" % (ref, what),
                            self.fix_next(c), self.unread_missing(c) + missing)
        # building
        on_main, why = self.work_on_main(c)
        if on_main is None:
            return self.set(c, "unknown", "It has linked work, but whether any of it is on main cannot be read",
                            self.fix_next(c), ["whether its work is on main: %s" % why])
        if on_main is False:
            ob = self.open_or_branch(c)
            if ob is True:
                reason, next_step = self.building(c)
                return self.set(c, "building", reason, next_step)
            stray = ", ".join("%s merged into %s" % (pr_name(p, self.p.project), p["base"])
                              for p in c.prs if p["state"] == "merged")
            if ob is None:
                return self.set(c, "unknown", "None of its work is on main (%s), and whether it has an open pull "
                                "request or a branch cannot be read" % stray, self.fix_next(c), self.unread_missing(c))
            return self.set(c, "unknown", "No row of the table matches: %s, which is not main, none of its work is "
                            "on main, and it has no open pull request and no branch" % stray,
                            "/loop-design %s" % ref,
                            ["a row of the derivation table for a pull request merged outside main (%s)" % stray])
        # merged
        env, served, error, serves = self.serves(c)
        commits, foreign, _ = self.merge_commits(c)
        shown = ", ".join([s[:7] for s in commits] + [pr_name(p, self.p.project) for p in foreign])
        if serves is False:
            return self.set(c, "merged", "Its work is on main (%s), and %s serves %s, which does not include it" % (
                shown, env, (served or "?")[:7]), "/loop-ship %s" % env)
        if serves is None:
            reason = ("Its work is on main (%s), and whether %s serves it cannot be read" % (shown, env)
                      if c.ships_to else "Its work is on main (%s), and the contract has no ships-to" % shown)
            return self.set(c, "unknown", reason, self.fix_next(c), self.serves_errors(c)
                            or ["the contract has no ships-to"])
        # shipped, stale, done
        results = [(claim, self.claim_result(c, claim)) for claim in c.live_claims()]
        missing_claims = [(cl, r) for cl, r in results if r[0] == "missing"]
        unknown_claims = [(cl, r) for cl, r in results if r[0] == "unknown"]
        stale_claims = [(cl, r) for cl, r in results if r[0] == "stale"]
        where = "%s serves its work" % env if env != "main" else "Main serves its work"
        if missing_claims:
            return self.set(c, "shipped", "%s, and %s" % (where, "; ".join(r[1] for _, r in missing_claims)),
                            "/loop-prove %s %s" % (ref, env))
        if unknown_claims:
            return self.set(c, "unknown", "%s, but %s" % (where, "; ".join(r[1] for _, r in unknown_claims)),
                            self.fix_next(c), [r[1] for _, r in unknown_claims])
        if stale_claims:
            return self.set(c, "stale", "; ".join(r[1] for _, r in stale_claims), "/loop-prove %s %s" % (ref, env))
        holds = "; ".join(r[1] for _, r in results) or "it has no claims"
        return self.set(c, "done", "Every claim has a current HOLDS on %s: %s" % (env, holds),
                        None if c.shipped_note else "Record a Shipped note (on your yes)")

    def building(self, c):
        open_prs = [p for p in c.prs if p["state"] == "open"]
        if not open_prs:
            return ("Its branch %s exists with no open pull request, and none of its work is on main" % c.ref,
                    "/loop-build %s, to resume %s: it has no pull request" % (c.ref, c.ref))
        ready = [p for p in open_prs if not p["draft"]]
        pr = ready[0] if ready else open_prs[0]
        name = pr_name(pr, self.p.project)
        if pr["draft"]:
            return ("%s is an open draft, and none of its work is on main" % name,
                    "Finish %s and mark it ready: it is a draft" % name)
        proof = proof_section(pr.get("body") or "")
        if pr["checks"] == "success" and proof:
            return ("%s is open and ready for review, and none of its work is on main" % name,
                    "The owner reviews %s: its checks are green and its body carries the proof" % name)
        if pr["checks"] in ("failure",):
            return ("%s is open and its checks fail, and none of its work is on main" % name,
                    "Fix %s: its checks fail" % name)
        if pr["checks"] in ("pending", "unknown"):
            return ("%s is open and its checks are %s, and none of its work is on main" % (name, pr["checks"]),
                    "Wait for %s's checks, then review it" % name)
        return ("%s is open, and none of its work is on main" % name,
                "Put the proof in %s's body (How it was proven before the merge)" % name)

    def unread_missing(self, c):
        out = ["%s: %s" % fe for fe in self.prs_unreadable(c)]
        if c.branch_exists is None:
            branches = self.p.facts.get("branches") or {}
            out.append("branches: %s" % (branches.get("error") or "not gathered"))
        return out

    def fix_next(self, c):
        """The next step for an unknown: whatever makes the missing fact readable."""
        text = " ".join(c.missing) + " " + " ".join(self.unread_missing(c))
        env = c.ships_to
        e = self.p.environment(env) if env else None
        if self.prs_unreadable(c) and ("gh" in text or "auth" in text or "pull request" in text):
            return "Authenticate gh (gh auth login), then /loop-status again"
        if e is not None and e["error"]:
            if "TODO" in e["error"] or "no served-commit command" in e["error"]:
                return "Fill in LOOP.md §3's served-commit command for %s, then /loop-status again" % env
            if "may not read" in e["error"]:
                return "Read what %s serves with the owner, then /loop-status again" % env
            return "Check that %s answers, then /loop-status again" % env
        if env and e is None and env != "main":
            return "Add a row named %s to LOOP.md §3, or correct ships-to, then /loop-status again" % env
        return "/loop-status again once the missing facts can be read"

    # Step 5.

    def goal_holds(self, loop, goal):
        if goal["struck"]:
            return None
        if is_ci_claim(goal["text"]):
            return True if self.p.ci == "success" else None if self.p.ci == "unknown" else False
        lines = [line for line in loop.evidence if line["key"] == goal["id"]]
        if not lines:
            return False
        last = lines[-1]
        if last["verdict"] != "HOLDS" or last["commit"] is None:
            return False
        env = self.p.environment(last["environment"]) if last["environment"] != "main" else {
            "served": self.p.main, "error": None}
        if env is None or env["error"]:
            return None
        value, _ = self.oracle.ask({"kind": "ancestor", "repository": self.p.project, "commit": last["commit"],
                                    "of": env["served"]})
        if value is not True:
            return value
        paths = sorted({p for c in loop.concerns for p in c.local_touches(self.p.project)})
        if paths:
            changed, _ = self.oracle.ask({"kind": "changes", "repository": self.p.project, "from": last["commit"],
                                          "to": env["served"], "paths": paths})
            if changed is None:
                return None
            if changed:
                return False
        return True

    def derive_loop(self, loop):
        if loop.parked:
            d = self.p.shared_decision(loop.id, loop.parked)
            loop.state, loop.reason, loop.next = "parked", "Its README has parked: %s%s" % (
                loop.parked, ", %s" % d["text"] if d else ""), None
            return
        if not loop.concerns:
            loop.state, loop.reason, loop.next = "open", "It has no concerns yet", "/loop-design %s" % loop.id
            return
        signals = []
        for c in loop.concerns:
            signals.append(True if (c.decisions or c.any_evidence) else self.built(c))
        if all(s is False for s in signals):
            loop.state, loop.reason, loop.next = "backlog", "None of its concerns has a decision, linked work or " \
                                                            "evidence", None
            return
        if not any(s is True for s in signals):
            loop.state = "unknown"
            loop.reason = ("None of its concerns has a decision or evidence, but whether one has linked work cannot "
                           "be read")
            loop.next = "Authenticate gh (gh auth login), then /loop-status again"
            return
        states = [c.state for c in loop.concerns]
        done = sum(1 for s in states if s == "done")
        goals = [(g, self.goal_holds(loop, g)) for g in loop.goals if not g["struck"]]
        if any(s not in ("done", "unknown") for s in states) or any(v is False for _, v in goals):
            loop.state = "active"
            loop.reason = "%d of its %d concerns %s done%s" % (done, len(states), "is" if done == 1 else "are", "" if
                                                              done < len(states) else ", and not every goal holds")
            loop.next = None
            return
        if any(s == "unknown" for s in states) or any(v is None for _, v in goals):
            unknown = [c.id for c in loop.concerns if c.state == "unknown"]
            loop.state = "unknown"
            loop.reason = "Every concern is done or unknown, and whether %s cannot be read, so done and active " \
                          "cannot be told apart" % (
                              "%s %s done" % (", ".join(unknown), "is" if len(unknown) == 1 else "are") if unknown
                              else "every goal holds")
            loop.next = "/loop-status %s/%s, to see what is missing" % (loop.id, unknown[0]) if unknown else \
                "/loop-status again once the missing facts can be read"
            return
        loop.state = "done"
        loop.reason = "Every concern is done, and %s" % ("every goal has a current HOLDS" if goals else
                                                         "it has no goals")
        loop.next = None if loop.shipped_note else "Record a Shipped note (on your yes)"

    # The document.

    def concern_doc(self, c):
        env, served, error, serves = self.serves(c)
        claims = []
        for claim in c.claims:
            claims.append({"id": claim["id"], "text": claim["text"], "struck": claim["struck"],
                           "evidence": [{k: line[k] for k in ("date", "verdict", "rung", "environment", "commit",
                                                              "text")} for line in c.lines(claim["id"])],
                           "current_holds": self.current_holds(c, claim)})
        inputs = {
            "main": self.p.main,
            "served": {"environment": c.ships_to, "commit": None if error else served, "error": error,
                       "serves": None if error else serves},
            "prs": [schema_pr(p, self.p.pr_on_main(p)[0]) for p in c.prs],
            "commits": list(c.commits),
            "branch": {"name": c.ref, "exists": c.branch_exists},
        }
        if c.merges:
            inputs["merges"] = list(c.merges)
        if c.missing:
            inputs["missing"] = list(c.missing)
        return {"id": c.id, "title": c.title, "path": c.path,
                "contract": {"needs": c.needs, "touches": c.touches, "effects": c.effects, "ships_to": c.ships_to,
                             "prs": c.pr_entries, "parked": c.parked},
                "claims": claims, "state": c.state, "reason": c.reason, "next": c.next, "inputs": inputs}

    def loop_doc(self, loop):
        owner, members = self.book.people(loop.id)
        return {"id": loop.id, "title": loop.title, "path": loop.path, "state": loop.state, "reason": loop.reason,
                "next": loop.next, "owner": owner, "members": members,
                "goals": [{"id": g["id"], "text": g["text"], "struck": g["struck"],
                           "evidence": [{k: line[k] for k in ("date", "verdict", "rung", "environment", "commit",
                                                              "text")} for line in loop.evidence
                                        if line["key"] == g["id"]],
                           "current_holds": self.goal_holds(loop, g)} for g in loop.goals],
                "concerns": [self.concern_doc(c) for c in loop.concerns]}

    def run(self):
        for c in self.p.concerns():
            self.derive_concern(c)
        for loop in self.p.loops:
            self.derive_loop(loop)
        doc = {
            "schema_version": SCHEMA_VERSION,
            "project": self.p.project,
            "as_of": self.p.facts.get("as_of") or "1970-01-01T00:00:00Z",
            "main": {"branch": self.p.main_branch, "sha": self.p.main, "ci": self.p.ci},
            "environments": [{"name": e["name"], "served": e["served"], "error": e["error"]}
                             for e in self.p.environments],
            "loops": [self.loop_doc(loop) for loop in self.p.loops],
            "queue": self.queue(),
            "agents_can_start": self.agents(),
            "drift": self.drift(),
            "missing": self.missing(),
        }
        return doc

    # Step 6: what needs a person.

    def unblocks(self, refs):
        out = list(dict.fromkeys(refs))
        first = len(out)
        changed = True
        while changed:
            changed = False
            for c in self.p.concerns():
                if c.state != "blocked" or c.ref in out:
                    continue
                needs = [k[1] for k in (self.p.resolve_need(c, n) for n in c.needs) if k[0] == "concern"]
                if any(n in out for n in needs):
                    out.append(c.ref)
                    changed = True
        return out[:first] + sorted(out[first:])

    def item(self, id_, kind, title, why, loop, concerns, unblocks, detail):
        return {"id": id_, "kind": kind, "title": title, "why": why, "loop": loop, "concerns": concerns,
                "unblocks": unblocks, "waits_on": None, "visible_to": [], "gate": None, "detail": detail}

    def queue(self):
        items = []
        live = [c for loop in self.p.loops if loop.state != "parked" for c in loop.concerns if c.state != "parked"]
        # Open questions.
        for loop in self.p.loops:
            if loop.state == "parked":
                continue
            sources = [(None, loop.questions)] + [(c, c.questions) for c in loop.concerns if c.state != "parked"]
            for owner, qs in sources:
                for q in qs:
                    if not q["open"]:
                        continue
                    blocked = [ref for ref, found in self.blocked_by.items() if q in found]
                    concerns = [owner.ref] if owner is not None else sorted(blocked)
                    why = ("%s blocks %s and is unanswered" % (q["number"], ", ".join(q["blocks"])) if blocked else
                           "%s is unanswered; it blocks nothing yet" % q["number"])
                    items.append(self.item(q["ref"], "question", q["question"], why, loop.id, concerns,
                                           self.unblocks(sorted(blocked)) if blocked else [],
                                           {"ref": q["ref"], "question": q["question"], "options": q["options"],
                                            "recommendation": q["recommendation"], "default": q["default"],
                                            "blocks": q["blocks"]}))
        # Pull requests ready for review.
        reviews = {}
        for c in live:
            for pr in c.prs:
                if pr["state"] == "open" and not pr["draft"] and pr["checks"] == "success" and proof_section(pr["body"]):
                    reviews.setdefault((pr["repository"], pr["number"]), (pr, []))[1].append(c)
        for (repo, number), (pr, cs) in sorted(reviews.items()):
            loops = {c.loop.id for c in cs}
            items.append(self.item("%s#%d" % (repo, number), "review", pr["title"],
                                   "Ready for review: its checks are green and its body carries the proof",
                                   loops.pop() if len(loops) == 1 else None, [c.ref for c in cs],
                                   self.unblocks([c.ref for c in cs]),
                                   {"pr": schema_pr(pr, self.p.pr_on_main(pr)[0]), "proof": proof_section(pr["body"])}))
        # Merged concerns waiting to ship.
        ships = {}
        for c in live:
            if c.state == "merged":
                ships.setdefault(c.ships_to, []).append(c)
        # One item per gate the concerns' effects cross other than merge, plus one for deploy (step 6's addressing).
        for env, cs in sorted(ships.items()):
            for gate, refs, steps in self.book.split_ship([(c.ref, c.effects) for c in cs]):
                group = [c for c in cs if c.ref in refs]
                loops = {c.loop.id for c in group}
                names = [c.id for c in group]
                why = "%s %s merged, and %s does not serve %s yet" % (
                    " and ".join(names) if len(names) < 3 else ", ".join(names),
                    "is" if len(names) == 1 else "are", env, "it" if len(names) == 1 else "them")
                if gate == addressing.DEPLOY:
                    id_, title = "ship/%s" % env, "Ship %s to %s" % (", ".join(names), env)
                else:
                    id_, title = "ship/%s/%s" % (env, gate), "Ship %s to %s: %s" % (", ".join(names), env, gate)
                    why += "; %s effects cross %s" % ("its" if len(names) == 1 else "their", gate)
                item = self.item(id_, "ship", title, why, loops.pop() if len(loops) == 1 else None,
                                 [c.ref for c in group], self.unblocks([c.ref for c in group]),
                                 {"environment": env, "manual_steps": steps})
                item["gate"] = gate
                items.append(item)
        # UNPROVEN claims that need something only a person has.
        for c in live:
            for claim in c.live_claims():
                lines = c.lines(claim["id"])
                if not lines or lines[-1]["verdict"] != "UNPROVEN":
                    continue
                line = lines[-1]
                m = NEEDS_ONLY_RE.search(line["text"])
                if m:
                    missing, who = m.group("missing").strip(), m.group("who").strip()
                else:
                    m = ONLY_RE.search(line["text"])
                    if not m:
                        continue
                    missing, who = line["text"], m.group("who").strip()
                items.append(self.item("%s/%s" % (c.ref, claim["id"]), "proof", "%s's %s needs %s" % (
                    c.id, claim["id"], missing), "%s's latest verdict is UNPROVEN on %s: only %s can supply %s" % (
                    claim["id"], line["environment"], who, missing), c.loop.id, [c.ref], self.unblocks([c.ref]),
                    {"claim": "%s/%s" % (c.ref, claim["id"]), "environment": line["environment"], "missing": missing,
                     "supplied_by": who, "command": "/loop-prove %s %s" % (c.ref, line["environment"])}))
        # Contradictions that need a call.
        for c in live:
            if c.state != "contradicted":
                continue
            for claim, line in c.contradictions:
                m = CONTRADICTS_REF_RE.search(line["text"])
                contradicts = m.group(1) if m else "%s, %s: %s" % (c.path, claim["id"], claim["text"])
                items.append(self.item(
                    "%s/%s" % (c.ref, claim["id"]), "contradiction",
                    "%s's %s is contradicted: redesign it, or roll back?" % (c.id, claim["id"]),
                    "%s CONTRADICTS on %s (rung %d, %s), and no decision is dated after it%s" % (
                        claim["id"], line["environment"], line["rung"], line["date"],
                        "; it contradicts %s, a shared decision" % m.group(1) if m else ""),
                    c.loop.id, [c.ref], self.unblocks([c.ref]),
                    {"claim": "%s/%s" % (c.ref, claim["id"]),
                     "evidence": {k: line[k] for k in ("date", "verdict", "rung", "environment", "commit", "text")},
                     "contradicts": contradicts, "escalates": bool(m), "command": "/loop-design %s" % c.ref}))
        # Loop-document pull requests that check_loop_pr.sh refused.
        prs = {(p["repository"], p["number"]): p for e in self.p.pr_facts.values() for p in e.get("items") or []}
        for check in sorted(self.p.facts.get("loop_document_checks") or [], key=lambda x: x["number"]):
            pr = prs.get((check["repository"], check["number"]))
            if pr is None or check.get("ok") is not False:
                continue
            loop = next((l.id for l in sorted(self.p.loops, key=lambda l: -len(l.id))
                         if pr["head"].startswith("docs/%s-" % l.id)), None)
            items.append(self.item("%s#%d" % (pr["repository"], pr["number"]), "refused_pr", pr["title"],
                                   "check_loop_pr.sh refused it, so no agent may merge it", loop, [], [],
                                   {"pr": schema_pr(pr, None), "failures": check.get("failures") or
                                    ["check_loop_pr.sh exited 1"],
                                    "command": "scripts/check_loop_pr.sh --pr %d" % pr["number"]}))
        # Records, on the owner's yes.
        for loop in self.p.loops:
            for c in loop.concerns:
                if c.state == "done" and not c.shipped_note:
                    items.append(self.item("record/%s" % c.ref, "record", "Add a Shipped note to %s" % c.id,
                                           "%s is done and has no Shipped note" % c.id, loop.id, [c.ref], [],
                                           {"path": c.path, "text": self.record_text(c)}))
            if loop.state == "done" and not loop.shipped_note:
                items.append(self.item("record/%s" % loop.id, "record", "Add a Shipped note to the %s loop" % loop.id,
                                       "%s is done and has no Shipped note" % loop.id, loop.id,
                                       [c.ref for c in loop.concerns], [],
                                       {"path": loop.path, "text": "Done: every concern (%s) is done, and %s." % (
                                           ", ".join(c.id for c in loop.concerns),
                                           "every goal has a current HOLDS" if loop.goals else "it has no goals")}))
        for item in items:
            self.book.address(item)
        items.sort(key=lambda i: (-len(i["unblocks"]), QUEUE_ORDER.index(i["kind"]), i["id"]))
        return items

    def record_text(self, c):
        env, served, _, _ = self.serves(c)
        prs = [pr_name(p, self.p.project) + (" (%s)" % p["merge_commit"][:7] if p["merge_commit"] else "")
               for p in c.prs if p["state"] == "merged" and self.p.pr_on_main(p)[0]]
        work = ", ".join(prs) or ", ".join(s[:7] for s in c.commits) or "its commits"
        holds = "; ".join(self.claim_result(c, cl)[1] for cl in c.live_claims()) or "it has no claims"
        return "Shipped to %s in %s. Every claim has a current HOLDS on %s @%s: %s." % (
            env, work, env, (served or self.p.main)[:7], holds)

    # Step 7.

    def agents(self):
        build, prove, design = [], [], []
        for loop in self.p.loops:
            if loop.state == "parked":
                continue
            for c in loop.concerns:
                if c.state == "ready":
                    build.append({"concern": c.ref, "action": "build", "command": "/loop-build %s" % c.ref})
                elif c.state in ("shipped", "stale"):
                    prove.append({"concern": c.ref, "action": "prove",
                                  "command": "/loop-prove %s %s" % (c.ref, c.ships_to)})
                elif c.state == "open" and c.open_by_contract:
                    design.append({"concern": c.ref, "action": "design", "command": "/loop-design %s" % c.ref})
        # What would meet a blocked concern's needs: proving a need whose work is on main (command-center/D50).
        for loop in self.p.loops:
            if loop.state == "parked":
                continue
            for c in loop.concerns:
                if c.state != "blocked":
                    continue
                for entry in c.prove_needs:
                    if not any(a["command"] == entry["command"] for a in prove):
                        prove.append({"concern": entry["concern"], "action": "prove", "command": entry["command"]})
        return build + prove + design

    # Step 8: drift the facts can show.

    def needs_between(self, a, b):
        def reach(start):
            seen, todo = set(), [start]
            while todo:
                c = self.p.by_ref[todo.pop()]
                for n in c.needs:
                    kind = self.p.resolve_need(c, n)
                    if kind[0] == "concern" and kind[1] not in seen:
                        seen.add(kind[1])
                        todo.append(kind[1])
            return seen
        return b.ref in reach(a.ref) or a.ref in reach(b.ref)

    def drift(self):
        out = []
        unmerged = ("open", "blocked", "ready", "building")
        candidates = [c for loop in self.p.loops if loop.state != "parked" for c in loop.concerns
                      if c.state in unmerged]
        for i, a in enumerate(candidates):
            for b in candidates[i + 1:]:
                if a.loop is not b.loop and not (a.loop.state == "active" and b.loop.state == "active"):
                    continue
                shared = []
                for ra, pa in a.touch_paths:
                    for rb, pb in b.touch_paths:
                        hit = paths_overlap(pa, pb) if ra == rb else None
                        if hit and hit not in shared:
                            shared.append(hit)
                if shared and not self.needs_between(a, b):
                    out.append({"where": "%s and %s, touches" % (a.path, b.path),
                                "finding": "%s and %s both touch %s, neither is merged, and neither needs the other"
                                           % (a.ref, b.ref, ", ".join(shared)),
                                "checked": "touches and needs in both contracts"})
        for c in self.p.concerns():
            if c.loop.state == "parked" or c.state == "parked":
                continue
            built = self.built(c) is True
            for pr in c.prs:
                if pr["state"] == "closed" or not pr["files"]:
                    continue
                touches = [p for r, p in c.touch_paths if r == pr["repository"]]
                if not touches:
                    continue
                outside = [f for f in pr["files"] if not any(path_matches(t, f) for t in touches)]
                if outside:
                    out.append({"where": "%s#%d, linked to %s" % (pr["repository"], pr["number"], c.ref),
                                "finding": "changes %s, outside %s's touches (%s)" % (
                                    ", ".join(outside[:5]) + (" and %d more" % (len(outside) - 5)
                                                              if len(outside) > 5 else ""),
                                    c.id, ", ".join(touches)),
                                "checked": "gh pr view %d --repo %s --json files" % (pr["number"], pr["repository"])})
            if built:
                lacks = [n for n, m in (("touches", not c.touches), ("ships-to", not c.ships_to),
                                        ("Done when", not c.live_claims())) if m]
                if lacks:
                    out.append({"where": "%s, contract" % c.path,
                                "finding": "%s is built, but its contract lacks %s, so %s cannot be checked" % (
                                    c.id, " and ".join(lacks), "staleness and overlap" if "touches" in lacks else
                                    "where it ships"),
                                "checked": "its front matter and Done when"})
                for d in self.needed_decisions_superseded(c):
                    out.append({"where": "%s, needs" % c.path,
                                "finding": "%s is built against %s, which has been superseded" % (c.id, d),
                                "checked": "the Shared decisions table"})
            if c.state == "building":
                behind = []
                for need in c.needs:
                    kind = self.p.resolve_need(c, need)
                    if kind[0] == "concern":
                        other = self.p.by_ref[kind[1]]
                        if other.state is not None and self.need_met(other)["met"] is False:
                            behind.append("%s %s" % (other.ref, self.need_met(other)["detail"]))
                if behind:
                    out.append({"where": "%s, needs" % c.path,
                                "finding": "%s is being built ahead of what it needs, which is not met: %s" % (
                                    c.id, "; ".join(behind)),
                                "checked": "each need's evidence and work on main (command-center/D50)"})
                if c.branch_head:
                    base, _ = self.oracle.ask({"kind": "merge_base", "repository": self.p.project,
                                               "a": c.branch_head, "b": self.p.main})
                    if base:
                        changed, _ = self.oracle.ask({"kind": "changes", "repository": self.p.project, "from": base,
                                                      "to": self.p.main, "paths": [c.path]})
                        if changed:
                            out.append({"where": "%s, since %s started" % (c.path, c.ref),
                                        "finding": "its contract changed on main after its branch started from %s, "
                                                   "in %s" % (base[:7], ", ".join(s[:7] for s in changed)),
                                        "checked": "git log %s..%s -- %s" % (base[:7], self.p.main[:7], c.path)})
            for line in c.unreadable:
                out.append({"where": "%s, Evidence" % c.path, "finding": "an evidence line the format cannot read: %s"
                            % line, "checked": "the evidence line format in LOOP.md §6"})
            ids = {cl["id"] for cl in c.claims}
            for key in sorted({line["key"] for line in c.evidence if line["key"].startswith("C")} - ids):
                out.append({"where": "%s, Evidence" % c.path, "finding": "evidence about %s, which Done when does not "
                            "have" % key, "checked": "the claims under Done when"})
            if c.parked and not any(d["id"] == c.parked for d in c.decisions):
                out.append({"where": "%s, front matter" % c.path, "finding": "parked: %s names no decision in its "
                            "Decisions" % c.parked, "checked": "the Decisions table"})
        for loop in self.p.loops:
            for problem in loop.problems + [p for c in loop.concerns for p in c.problems]:
                out.append({"where": "%s:%d, Questions" % (problem["file"], problem["line"]),
                            "finding": problem["message"], "checked": "questions.py %s" % problem["file"]})
            for line in loop.unreadable:
                out.append({"where": "%s, Evidence" % loop.path, "finding": "an evidence line the format cannot "
                            "read: %s" % line, "checked": "the evidence line format in LOOP.md §6"})
            if not loop.exists:
                out.append({"where": loop.path, "finding": "the loop has no README.md", "checked": "the files on main"})
        # What step 6 could not address as written.
        live = [(loop, c) for loop in self.p.loops if loop.state != "parked" for c in [None] + loop.concerns
                if c is None or c.state != "parked"]
        out += list(self.book.drift)
        out += self.book.check([(c.path, e) for _, c in live if c is not None for e in c.effects],
                               [q for loop, c in live for q in (c.questions if c else loop.questions) if q["open"]])
        return out

    def missing(self):
        out = []
        f = self.p.facts
        if f.get("fetch", {}).get("error") if isinstance(f.get("fetch"), dict) else False:
            out.append({"fact": "git fetch", "error": f["fetch"]["error"]})
        if self.p.loop_md is None:
            out.append({"fact": "LOOP.md", "error": "there is no LOOP.md on main, so main is the only environment, "
                                                    "and merged and shipped cannot be told apart"})
        for repo in [self.p.project] + self.p.other_repositories():
            error = self.p.prs_missing(repo)
            if error:
                out.append({"fact": "pull requests" if repo == self.p.project else "pull requests in %s" % repo,
                            "error": error})
        if self.p.ci == "unknown":
            out.append({"fact": "checks on main @%s" % self.p.main[:7], "error": self.p.ci_error})
        for env in self.p.environments:
            if env["error"]:
                out.append({"fact": "%s's served commit" % env["name"], "error": env["error"]})
        for key, fact in (("branches", "branches"), ("trailers", "commits with a Concern trailer")):
            entry = f.get(key) or {}
            if entry.get("error") or not entry:
                out.append({"fact": fact, "error": entry.get("error") or "not gathered"})
        for repo in self.p.other_repositories():
            entry = self.p.repositories.get(repo)
            if entry is None or entry.get("error"):
                out.append({"fact": "%s's default branch" % repo, "error": (entry or {}).get("error") or
                            "not gathered"})
        for check in f.get("loop_document_checks") or []:
            if check.get("error"):
                out.append({"fact": "check_loop_pr.sh on #%d" % check["number"], "error": check["error"]})
        return out


def derive(facts):
    """The status document for a facts document. Pure: the same facts give the same document."""
    return Derivation(facts).run()


def pending_queries(facts):
    """The git questions the derivation asked that the facts do not answer yet. A caller that supplies its own facts
    answers these and adds them to facts["answers"], until none is left."""
    d = Derivation(facts)
    d.run()
    return d.oracle.pending


# --- Gathering -----------------------------------------------------------------------------------------------------

class Runner:
    """Runs read-only commands in the repository, and logs each one."""

    def __init__(self, cwd, env):
        self.cwd, self.env, self.log = cwd, env, []

    def run(self, argv, shell=False, data=None, timeout=300, cwd=None, extra_env=None, binary=False):
        env = dict(self.env, **(extra_env or {}))
        try:
            r = subprocess.run(argv, shell=shell, cwd=cwd or self.cwd, env=env, input=data, capture_output=True,
                               timeout=timeout)
            code, out, err = r.returncode, r.stdout, r.stderr
        except FileNotFoundError as e:
            code, out, err = 127, b"", str(e).encode()
        except subprocess.TimeoutExpired:
            code, out, err = 124, b"", ("timed out after %d s" % timeout).encode()
        self.log.append({"command": argv if shell else shlex.join(argv), "exit": code})
        err = err.decode("utf-8", "replace")
        return code, (out if binary else out.decode("utf-8", "replace")), err


def last_line(text, code):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else "exit %d" % code


def project_from_url(url):
    m = re.search(r"github\.com[:/]+([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$", url.strip())
    return "%s/%s" % (m.group(1), m.group(2)) if m else None


def gather(root=".", project=None, as_of=None, fetch=True, env=None, main=None):
    """Read every fact the derivation needs, read-only, and answer its git questions. Returns a facts document."""
    env = dict(os.environ if env is None else env)
    run = Runner(root, env)
    code, top, err = run.run(["git", "rev-parse", "--show-toplevel"])
    if code:
        raise FactsError("not a git repository: %s (%s)" % (os.path.abspath(root), last_line(err, code)))
    run.cwd = top.strip()
    facts = {"facts_version": FACTS_VERSION}
    code, origin_url, _ = run.run(["git", "remote", "get-url", "origin"])
    origin_url = origin_url.strip() if code == 0 else None
    if fetch and origin_url:
        code, _, err = run.run(["git", "fetch", "--prune", "--quiet", "origin"])
        if code:
            facts["fetch"] = {"error": last_line(err, code)}
    branch = main
    if branch is None:
        code, out, _ = run.run(["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"])
        branch = out.strip().split("/", 1)[1] if code == 0 and "/" in out else "main"
    ref = "origin/%s" % branch if origin_url else branch
    code, sha, err = run.run(["git", "rev-parse", "--verify", "--quiet", "%s^{commit}" % ref])
    if code and origin_url:
        ref = branch
        code, sha, err = run.run(["git", "rev-parse", "--verify", "--quiet", "%s^{commit}" % ref])
    if code:
        raise FactsError("no %s branch to read in %s" % (branch, run.cwd))
    sha = sha.strip()
    facts["main"] = {"branch": branch, "sha": sha, "error": None}

    # The loop documents and LOOP.md, as they are on main.
    code, out, err = run.run(["git", "ls-tree", "-r", "-z", "--name-only", sha, "--", "LOOP.md", "docs/loops"])
    paths = [p for p in out.split("\0") if p == "LOOP.md" or re.match(r"^docs/loops/[^/]+/[^/]+\.md$", p)]
    files = {}
    if paths:
        code, blob, err = run.run(["git", "cat-file", "--batch"], binary=True,
                                  data="".join("%s:%s\n" % (sha, p) for p in paths).encode())
        at = 0
        for p in paths:
            end = blob.index(b"\n", at)
            header = blob[at:end].decode().split()
            at = end + 1
            if len(header) == 3 and header[1] == "blob":
                size = int(header[2])
                files[p] = blob[at:at + size].decode("utf-8", "replace")
                at += size + 1
    facts["files"] = files

    if not project:
        project = project_from_url(origin_url or "")
    if not project:
        code, out, _ = run.run(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"])
        project = out.strip() if code == 0 and "/" in out else None
    facts["project"] = project or os.path.basename(run.cwd)
    facts["as_of"] = as_of or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # What each environment serves.
    rows = environment_rows(files.get("LOOP.md"))
    environments = []
    if not any(row["name"] == "main" for row in rows):
        environments.append({"name": "main", "served": sha, "error": None})
    for row in rows:
        if row["error"]:
            environments.append({"name": row["name"], "served": None, "error": row["error"]})
            continue
        code, out, err = run.run(row["command"], shell=True, timeout=120)
        found = [line.strip().lower() for line in out.splitlines() if SHA_RE.match(line.strip().lower())]
        found = found or FULL_SHA_RE.findall(out.lower())
        if code:
            environments.append({"name": row["name"], "served": None,
                                 "error": "`%s` exited %d: %s" % (row["command"], code, last_line(err or out, code))})
        elif not found:
            environments.append({"name": row["name"], "served": None,
                                 "error": "`%s` printed no commit" % row["command"]})
        else:
            environments.append({"name": row["name"], "served": found[-1], "error": None})
    facts["environments"] = environments

    # Checks on main.
    code, out, err = run.run(["gh", "run", "list", "--repo", facts["project"], "--commit", sha, "--limit", "100",
                              "--json", "status,conclusion,workflowName"])
    try:
        facts["ci"] = {"commit": sha, "state": runs_state(json.loads(out)), "error": None} if code == 0 else \
            {"commit": sha, "state": "unknown", "error": last_line(err, code)}
    except ValueError:
        facts["ci"] = {"commit": sha, "state": "unknown", "error": "gh run list printed no JSON"}

    # Pull requests, in this repository and every other one a touches or prs entry names.
    facts["pull_requests"], facts["repositories"] = [], []
    model = Project(dict(facts, branches={"heads": {}, "error": None}, trailers={"commits": [], "error": None},
                         pull_requests=[], answers=[]))
    wanted = {}
    for c in model.concerns():
        for repo, number in c.pr_refs:
            wanted.setdefault(repo, set()).add(number)
    for repo in [facts["project"]] + model.other_repositories():
        code, out, err = run.run(["gh", "pr", "list", "--repo", repo, "--state", "all", "--limit", "300", "--json",
                                  PR_FIELDS])
        entry = {"repository": repo, "items": [], "error": None}
        try:
            entry["items"] = [normalize_pr(p, repo) for p in json.loads(out)] if code == 0 else []
            if code:
                entry["error"] = last_line(err, code)
        except ValueError:
            entry["error"] = "gh pr list printed no JSON"
        if not entry["error"]:
            for number in sorted(wanted.get(repo, set()) - {p["number"] for p in entry["items"]}):
                code, out, err = run.run(["gh", "pr", "view", str(number), "--repo", repo, "--json", PR_FIELDS])
                if code == 0:
                    try:
                        entry["items"].append(normalize_pr(json.loads(out), repo))
                    except ValueError:
                        pass
        facts["pull_requests"].append(entry)
        if repo != facts["project"]:
            code, out, err = run.run(["gh", "api", "repos/%s" % repo, "--jq", ".default_branch"])
            facts["repositories"].append({"repository": repo, "default_branch": out.strip() or None
                                          if code == 0 else None, "error": None if code == 0 and out.strip()
                                          else last_line(err, code)})

    # Branches, trailers and merge commits, from git.
    if origin_url:
        code, out, err = run.run(["git", "for-each-ref", "--format=%(refname:strip=3)%09%(objectname)",
                                  "refs/remotes/origin"])
    else:
        code, out, err = run.run(["git", "for-each-ref", "--format=%(refname:strip=2)%09%(objectname)", "refs/heads"])
    heads = dict(line.split("\t", 1) for line in out.splitlines() if "\t" in line)
    heads.pop("HEAD", None)
    facts["branches"] = {"heads": heads if code == 0 else None, "error": None if code == 0 else last_line(err, code)}
    code, out, err = run.run(["git", "log", sha, "--format=%H%x09%(trailers:key=Concern,valueonly,separator=%x2C)"])
    commits = []
    for line in out.splitlines():
        commit, _, refs = line.partition("\t")
        refs = [r.strip() for r in refs.split(",") if r.strip()]
        if refs:
            commits.append({"sha": commit, "concerns": refs})
    facts["trailers"] = {"commits": commits, "error": None if code == 0 else last_line(err, code)}
    code, out, err = run.run(["git", "log", "--first-parent", sha, "--format=%H%x09%s"])
    merges = []
    for line in out.splitlines():
        commit, _, subject = line.partition("\t")
        if MERGE_SUBJECT_RE.match(subject) or SQUASH_SUBJECT_RE.search(subject):
            merges.append({"sha": commit, "subject": subject})
    facts["merges"] = {"commits": merges, "error": None if code == 0 else last_line(err, code)}

    # check_loop_pr.sh on each open loop-document pull request, in a throwaway clone.
    facts["loop_document_checks"] = []
    loop_ids = sorted({p.split("/")[2] for p in files if p.startswith("docs/loops/")}, key=len, reverse=True)
    project_prs = next((e for e in facts["pull_requests"] if e["repository"] == facts["project"]), {})
    for pr in project_prs.get("items") or []:
        if pr["state"] != "open" or pr["draft"] or pr["base"] != branch:
            continue
        if not any(pr["head"].startswith("docs/%s-" % loop_id) for loop_id in loop_ids):
            continue
        facts["loop_document_checks"].append(check_loop_pr(run, pr, origin_url, sha, branch, facts["project"]))

    # The git questions the derivation asks, answered until none is left.
    facts["answers"] = []
    for _ in range(8):
        pending = pending_queries(facts)
        if not pending:
            break
        for query in pending:
            facts["answers"].append(answer(run, query, facts["project"]))
    facts["log"] = run.log
    return facts


def check_loop_pr(run, pr, origin_url, main_sha, branch, project):
    out = {"repository": pr["repository"], "number": pr["number"], "head": None, "ok": None, "failures": [],
           "error": None}
    checker = os.path.join(HERE, "check_loop_pr.sh")
    if not origin_url:
        out["error"] = "no origin to fetch pull/%d/head from" % pr["number"]
        return out
    tmp = tempfile.mkdtemp(prefix="loop-status-check-")
    clone = os.path.join(tmp, "repo")
    try:
        steps = [
            (["git", "clone", "--quiet", "--shared", "--no-checkout", run.cwd, clone], None),
            (["git", "fetch", "--quiet", origin_url, "refs/pull/%d/head" % pr["number"]], clone),
            (["git", "checkout", "--quiet", "--detach", "FETCH_HEAD"], clone),
            (["git", "update-ref", "refs/remotes/origin/%s" % branch, main_sha], clone),
        ]
        for argv, cwd in steps:
            code, _, err = run.run(argv, cwd=cwd)
            if code:
                out["error"] = "%s: %s" % (" ".join(argv[:2]), last_line(err, code))
                return out
        code, head, _ = run.run(["git", "rev-parse", "HEAD"], cwd=clone)
        out["head"] = head.strip() or None
        code, text, err = run.run(["sh", checker, "--base", "origin/%s" % branch, "--pr", str(pr["number"])],
                                  cwd=clone, extra_env={"GH_REPO": project})
        if code == 0:
            out["ok"] = True
        elif code == 1:
            out["ok"] = False
            out["failures"] = [line.strip() for line in text.splitlines() if line.startswith("FAIL")]
        else:
            out["error"] = "check_loop_pr.sh exited %d: %s" % (code, last_line(err or text, code))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


def answer(run, query, project):
    """Answer one git question: with git for this repository, with gh's compare API for another one."""
    kind = query["kind"]
    out = {"query": query, "value": None, "error": None}
    if kind == "ancestor" and query["repository"] != project:
        code, text, err = run.run(["gh", "api", "repos/%s/compare/%s...%s" % (query["repository"], query["commit"],
                                                                             query["of"]), "--jq", ".status"])
        status = text.strip()
        if code == 0 and status in ("ahead", "identical", "behind", "diverged"):
            out["value"] = status in ("ahead", "identical")
        else:
            out["error"] = last_line(err or text, code)
        return out
    if query["repository"] != project:
        out["error"] = "%s questions about %s cannot be answered from this repository" % (kind, query["repository"])
        return out
    if kind == "ancestor":
        code, _, err = run.run(["git", "merge-base", "--is-ancestor", query["commit"], query["of"]])
        if code in (0, 1):
            out["value"] = code == 0
        else:
            out["error"] = last_line(err, code)
    elif kind == "changes":
        code, text, err = run.run(["git", "log", "--format=%H", "%s..%s" % (query["from"], query["to"]), "--"]
                                  + query["paths"])
        if code == 0:
            out["value"] = [line.strip() for line in text.splitlines() if line.strip()]
        else:
            out["error"] = last_line(err, code)
    elif kind == "merge_base":
        code, text, err = run.run(["git", "merge-base", query["a"], query["b"]])
        if code == 0 and text.strip():
            out["value"] = text.strip()
        else:
            out["error"] = last_line(err, code) if code != 1 else "no common ancestor"
    else:
        out["error"] = "unknown question %r" % kind
    return out


# --- The board -----------------------------------------------------------------------------------------------------

def claim_summary(claim, ci):
    if claim["struck"]:
        return None
    lines = claim["evidence"]
    if is_ci_claim(claim["text"]) and not (lines and lines[-1]["verdict"] == "CONTRADICTS"):
        holds = {True: "holds", False: "not yet", None: "unknown"}[claim["current_holds"]]
        return "%s by CI on main (%s): %s" % (claim["id"], ci, holds)
    if not lines:
        return "%s no evidence" % claim["id"]
    last = lines[-1]
    return "%s %s rung %d %s @%s" % (claim["id"], last["verdict"], last["rung"], last["environment"],
                                     (last["commit"] or "?")[:7])


def table(rows, widths=None):
    widths = widths or [max(len(str(r[i])) for r in rows) for i in range(len(rows[0]))]
    return ["  ".join(str(cell).ljust(widths[i]) if i < len(row) - 1 else str(cell) for i, cell in enumerate(row))
            .rstrip() for row in rows]


def header(doc, loop):
    envs = ["%s serves %s" % (env["name"], env["served"][:7]) for env in doc["environments"]
            if env["name"] != "main" and env["served"]]
    unknown = [env["name"] for env in doc["environments"] if env["name"] != "main" and not env["served"]]
    if unknown:
        envs.append("unknown: %s" % ", ".join(unknown))
    stamp = doc["as_of"].replace("T", " ").replace("Z", " UTC")
    parts = ["%s · %d concern%s · main %s (CI %s)" % (loop["id"], len(loop["concerns"]),
                                                      "" if len(loop["concerns"]) == 1 else "s",
                                                      doc["main"]["sha"][:7], doc["main"]["ci"])] + envs + [stamp]
    return " · ".join(parts)


def loop_board(doc, loop):
    lines = [header(doc, loop), "%s: %s" % (loop["state"], loop["reason"])]
    if loop["concerns"]:
        lines.append("")
        rows = [("concern", "state", "evidence", "next")]
        for c in loop["concerns"]:
            evidence = "; ".join(s for s in (claim_summary(cl, doc["main"]["ci"]) for cl in c["claims"]) if s) or "—"
            rows.append((c["id"], c["state"], evidence, c["next"] or "—"))
        lines += table(rows)
    return lines


def concern_view(doc, ref):
    loop = next(l for l in doc["loops"] if l["id"] == ref.split("/")[0])
    c = next(x for x in loop["concerns"] if x["id"] == ref.split("/")[1])
    inputs, contract = c["inputs"], c["contract"]
    served = inputs["served"]

    def row(label, value, source=None):
        return "%-10s%s%s" % (label, value, "   (from: %s)" % source if source else "")

    out = ["%s · %s" % (ref, c["title"]), row("state", c["state"]), row("reason", c["reason"]),
           row("next", c["next"] or "—"),
           row("contract", "needs %s · touches %s · ships-to %s · effects %s%s" % (
               ", ".join(contract["needs"]) or "—", ", ".join(contract["touches"]) or "—",
               contract["ships_to"] or "—", "; ".join(contract["effects"]) or "—",
               " · parked %s" % contract["parked"] if contract["parked"] else ""), c["path"] + " on main"),
           "claims"]
    for claim in c["claims"]:
        holds = "struck, counts for nothing" if claim["struck"] else "current HOLDS: %s" % {
            True: "yes", False: "no", None: "unknown"}[claim["current_holds"]]
        out.append("  %s %s · %s" % (claim["id"], holds, claim["text"]))
        for line in claim["evidence"]:
            out.append("    %s · %s · rung %d · %s @%s · %s" % (line["date"], line["verdict"], line["rung"],
                                                               line["environment"], line["commit"] or "?",
                                                               line["text"]))
    out.append("facts")
    out.append(row("  main", inputs["main"], "git rev-parse origin/main, after git fetch"))
    if served["environment"]:
        out.append(row("  served", "%s %s · serves its work: %s" % (
            served["environment"], served["commit"] or served["error"],
            {True: "yes", False: "no", None: "unknown"}[served["serves"]]),
            "LOOP.md §3's served-commit command for %s" % served["environment"]
            if served["environment"] != "main" else "the main branch's head"))
    for pr in inputs["prs"]:
        out.append(row("  pr", "%s#%d %s%s, %s → %s, merge %s, on main: %s, checks %s · %s" % (
            pr["repository"], pr["number"], pr["state"], " (draft)" if pr["draft"] else "", pr["head"], pr["base"],
            (pr["merge_commit"] or "—")[:7], {True: "yes", False: "no", None: "—"}[pr["on_main"]], pr["checks"],
            pr["url"]), "gh pr list; git merge-base --is-ancestor"))
    for sha in inputs["commits"]:
        out.append(row("  commit", sha[:7], "git log origin/main, Concern trailers"))
    branch = inputs.get("branch")
    if branch:
        out.append(row("  branch", "%s: %s" % (branch["name"], {True: "exists", False: "absent", None: "unknown"}[
            branch["exists"]]), "git for-each-ref refs/remotes/origin"))
    for fact in inputs.get("missing", []):
        out.append(row("  missing", fact))
    return out


def board(doc, scope=None):
    """The text board of loop-status's step 9, for every loop, one loop, or one concern."""
    loops = doc["loops"]
    if scope:
        parts = scope.split("/")
        known = {l["id"]: {c["id"] for c in l["concerns"]} for l in loops}
        if len(parts) > 2 or parts[0] not in known or (len(parts) == 2 and parts[1] not in known[parts[0]]):
            raise ValueError("no loop or concern named %s" % scope)
        if len(parts) == 2:
            return "\n".join(concern_view(doc, scope)) + "\n"
        loops = [l for l in loops if l["id"] == scope]
    lines = []
    for loop in loops:
        if scope or loop["state"] in ("active", "unknown", "open"):
            lines += loop_board(doc, loop) + [""]
    brief = [l for l in loops if not scope and l["state"] not in ("active", "unknown", "open")]
    for loop in brief:
        lines.append("%s · %s · %d concern%s · %s" % (loop["id"], loop["state"], len(loop["concerns"]),
                                                     "" if len(loop["concerns"]) == 1 else "s", loop["reason"]))
    if brief:
        lines.append("")
    ids = {l["id"] for l in loops}

    def in_scope(item):
        return not scope or item["loop"] in ids or any(c.split("/")[0] in ids for c in item["concerns"])

    queue = [i for i in doc["queue"] if in_scope(i)]
    needs = [i for i in queue if i["kind"] != "record"]
    records = [i for i in queue if i["kind"] == "record"]
    lines.append("Needs you (%d), most unblocking first" % len(needs))
    for n, item in enumerate(needs, 1):
        command = item["detail"].get("command") if item["kind"] in ("proof", "contradiction", "refused_pr") else None
        lines.append("  %d. %s · %s · %s%s%s · waits on %s%s" % (
            n, item["kind"], item["title"], item["why"],
            " · unblocks %d" % len(item["unblocks"]) if item["unblocks"] else "",
            " · run %s" % command if command else "", item["waits_on"] or "no one named",
            " (gate: %s)" % item["gate"] if item["gate"] else ""))
    starts = [s for s in doc["agents_can_start"] if not scope or s["concern"].split("/")[0] in ids]
    lines.append("Agents can start now (%d)" % len(starts))
    lines += ["  %s" % s["command"] for s in starts]
    drift = [d for d in doc["drift"] if not scope or any("docs/loops/%s/" % i in d["where"] or
                                                          " %s/" % i in " " + d["where"] for i in ids)]
    lines.append("Drift (%d)" % len(drift))
    lines += ["  %s: %s (checked: %s)" % (d["where"], d["finding"], d["checked"]) for d in drift]
    lines.append("Record (%d), on your yes" % len(records))
    lines += ["  %s: %s" % (r["detail"]["path"], r["detail"]["text"]) for r in records]
    if doc["missing"]:
        lines.append("Missing (%d)" % len(doc["missing"]))
        lines += ["  %s: %s" % (m["fact"], m["error"]) for m in doc["missing"]]
    return "\n".join(lines) + "\n"


# --- The command line ----------------------------------------------------------------------------------------------

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    command = argv.pop(0) if argv and argv[0] in ("gather", "derive") else "both"
    parser = argparse.ArgumentParser(prog="loop_status.py", description="Derive where every loop and concern stands, "
                                     "from facts. With no subcommand, gather the facts and derive the board.")
    parser.add_argument("scope", nargs="?", help="<loop> or <loop>/<concern>: what the board shows")
    parser.add_argument("--json", action="store_true", help="print the status document instead of the board")
    parser.add_argument("--facts", help="derive: the facts document to read, or - for stdin")
    parser.add_argument("--repo", default=".", help="the repository to gather from (default: .)")
    parser.add_argument("--project", help="the project's key, owner/name")
    parser.add_argument("--main", help="the main branch")
    parser.add_argument("--as-of", help="when the facts were gathered, YYYY-MM-DDTHH:MM:SSZ")
    parser.add_argument("--no-fetch", action="store_true", help="do not run git fetch first")
    args = parser.parse_args(argv)

    def fail(message):
        sys.stderr.write("loop_status.py: %s\n" % message)
        return 2

    if args.as_of and not AS_OF_RE.match(args.as_of):
        return fail("--as-of must look like 2026-10-21T09:00:00Z")
    if command == "derive" and not args.facts:
        return fail("derive needs --facts FILE (or - for stdin)")
    if command == "gather" and (args.scope or args.json):
        return fail("gather prints the facts document; it takes no scope and no --json")
    try:
        if command == "derive":
            if args.facts == "-":
                facts = json.load(sys.stdin)
            else:
                with open(args.facts, encoding="utf-8") as f:
                    facts = json.load(f)
        else:
            facts = gather(args.repo, project=args.project, as_of=args.as_of, fetch=not args.no_fetch,
                           main=args.main)
            if command == "gather":
                json.dump(facts, sys.stdout, indent=1, ensure_ascii=False)
                sys.stdout.write("\n")
                return 0
        doc = derive(facts)
        if args.json:
            json.dump(doc, sys.stdout, indent=2, ensure_ascii=False)
            sys.stdout.write("\n")
        else:
            sys.stdout.write(board(doc, args.scope))
    except (FactsError, ValueError, OSError, KeyError, TypeError) as e:
        return fail(str(e))
    return 0


if __name__ == "__main__":
    sys.exit(main())
