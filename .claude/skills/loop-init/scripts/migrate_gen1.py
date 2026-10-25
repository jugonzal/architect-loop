#!/usr/bin/env python3
"""Migrate a project from generation 1 of the Architect Loop skills to generation 2.

Usage:
    python3 migrate_gen1.py [--repo PATH] [--apply] [--only SLUG]... [--include-done]
                            [--no-mark] [--today YYYY-MM-DD]

Generation 1 kept each initiative in one proposal, `docs/proposals/<slug>.md`, with numbered
steps and status lines written by hand. Generation 2 keeps each loop in its own folder,
`docs/loops/<slug>/`: a README for the loop and one file per concern, with status derived from
facts rather than stored.

What it does
------------
- Finds the generation 1 proposals: the `.md` files in the proposals folder (the one LOOP.md §5
  names, else `docs/proposals/`) that have a line `**Status:** <State> — YYYY-MM-DD.` Other
  markdown files there are people's documents and are left alone.
- Proposed, Accepted and In progress proposals become loops (a Proposed one is a backlog loop).
  Done, Superseded and Parked ones stay where they are, as history. `--only` restricts the run to
  the slugs it names, and also migrates a history-state proposal it names.
- For each proposal it migrates, it writes `docs/loops/<slug>/README.md` (intent, goals, shared
  decisions and questions with their numbers kept) and one `<concern>.md` per unfinished plan
  step (its done-when, its approach, and its proof as evidence lines). Done steps stay in the
  history file; `--include-done` migrates them too.
- It adds one `**Migrated:**` line under the history file's Status line, pointing at the loop
  (`--no-mark` skips this).
- It reports, without changing anything, what `/loop-init` must still change in LOOP.md, and any
  generation 1 copies of the retired skills installed in `~/.claude/skills` or
  `<repo>/.claude/skills`.

By default it is a dry run: it prints the whole plan, with the reason for every classification,
and writes nothing. `--apply` writes exactly that plan. It is idempotent: a proposal whose
`docs/loops/<slug>/` already exists is skipped as already migrated, so a second `--apply`
changes nothing.

What it never does
------------------
It never edits LOOP.md, never deletes, moves or renames a file, never commits, pushes, stages or
switches a branch, never makes a network call (git is only read, offline), and never writes
anything except new files under `docs/loops/` and the one marker line in each history file.

Options
-------
--repo PATH        the repository (default: the current directory)
--apply            write the plan (default: dry run)
--only SLUG        migrate only this proposal; repeat for more
--include-done     also turn done steps into concerns
--no-mark          do not add the `**Migrated:**` line to history files
--today DATE       the date written into the files (default: today)

Exit status: 0 on success, including when there is nothing to migrate; 2 when `--repo` is not a
git repository, has no proposals folder, or an argument is invalid.

Standard library only; Python 3.8 or later.
"""

import argparse
import datetime
import os
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Tuple

TOOL = "migrate_gen1.py"
LOOPS_REL = "docs/loops"
DEFAULT_PROPOSALS_REL = "docs/proposals"
MIGRATE_STATES = ("proposed", "accepted", "in progress")
HISTORY_STATES = ("done", "superseded", "parked")
RETIRED_SKILLS = ("loop-frame", "loop-decide", "loop-promote", "loop-record", "loop-reconcile")
RETIRED_MARK = "Retired in architect-loop 0.2"
DEFAULT_ENVS = ("local", "dev", "development", "main", "staging", "production", "prod")
STOP_WORDS = {
    "a", "an", "the", "of", "to", "and", "for", "in", "on", "with", "its", "from", "at", "by",
}
MAX_SLUG_WORDS = 6
MAX_SLUG_CHARS = 50
MAX_TOUCHES = 6

DECISIONS_HEADER = "| # | Decision | Decided by, date | Notes |"
CONCERN_DECISIONS_HEADER = "| # | Decision | Decided by, date | Closes |"
QUESTIONS_HEADER = "| # | Question | Blocks | Default if unanswered |"
TABLE_SEP = "| --- | --- | --- | --- |"

STATUS_LINE_RE = re.compile(
    r"^\*\*Status:\*\*\s*(?P<state>[A-Za-z][A-Za-z ]*?)\s*[\u2014\u2013-]\s*(?P<date>\d{4}-\d{2}-\d{2})\b")
MIGRATED_LINE_RE = re.compile(r"^\*\*Migrated:\*\*")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
STEP_HEADING_RE = re.compile(
    r"^(?P<kind>Step|Phase|Wave)\s+(?P<id>\d+[A-Za-z]?|[A-Z]\d*[a-z]?)"
    r"\s*(?:(?:\u2014|\u2013|-|:)\s*(?P<title>.*))?$")
FIELD_NAMES = r"Does|Done when|Gate|Status|Proof"
FIELD_RE = re.compile(
    r"^(?:[-*+]\s+)?(?:"
    r"\*\*(?P<n1>" + FIELD_NAMES + r")\b(?P<l1>[^*:]*?)\s*(?::\*\*|\*\*\s*:)"
    r"|\*\*(?P<n2>" + FIELD_NAMES + r")\*\*\s*(?P<l2>\([^)]*\))\s*:"
    r")\s?(?P<rest>.*)$", re.I)
LOOSE_STATUS_RE = re.compile(r"^\s*[*_]{1,2}Status\b(?P<extra>[^:*_]{0,40}):\s*(?P<rest>.*?)\s*[*_]{0,2}\s*$")
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
DATE_EXT_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:/\d{1,2})?\b")
HEX_TOKEN_RE = re.compile(r"(?<![0-9A-Za-z_])[0-9a-f]{7,40}(?![0-9A-Za-z_])")
BACKTICK_HEX_RE = re.compile(r"`([0-9a-f]{7,40})`")
VERDICT_RE = re.compile(r"\b(HOLDS|CONTRADICTS|UNPROVEN)\b")
RUNG_RE = re.compile(r"\brung\s*(\d)\b", re.I)
PR_RE = re.compile(r"(?<![\w/#&])(?:(?P<repo>[A-Za-z0-9][\w.-]*/[\w.-]+))?#(?P<num>\d+)\b")
STEP_REF_RE = re.compile(
    r"(?i:\b(?:after|needs?|requires?|waits?\s+for|depends\s+on)\s+(?:steps?|phases?|waves?))\s+"
    r"(?P<ids>(?:\d+[a-z]?|[A-Z]\b)(?:\s*(?:,|and|&|\u2013|\u2014|-|to)\s*(?:\d+[a-z]?|[A-Z]\b))*)")
DECISION_REF_RE = re.compile(r"\bD(\d+)\b")
SEP_ROW_RE = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
GOAL_RE = re.compile(r"^[-*+]\s+(?:~~)?\*\*G\d+")
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
UNFINISHED_RE = re.compile(
    r"\b(?:not\s+(?:yet\s+)?(?:run|done|built|merged|proven|started|verified|deployed|shipped|enabled|met|"
    r"finished|complete)"
    r"|not\b[^.;]{0,40}\byet\b"
    r"|still\s+(?:to|open|pending|unproven|waiting|missing|needs?)"
    r"|wait(?:s|ing)?\s+(?:for|on)"
    r"|pending|unproven|contradict\w*"
    r"|flag[- ]off|flag\s+is\s+off|behind\s+(?:a|the|its)\b[^.;]{0,40}\bflag"
    r"|partly|partial(?:ly)?|in\s+progress|blocked|remains?\s+open|todo)\b", re.I)


# ---------------------------------------------------------------------------------------------
# Small text helpers


def one_line(text: str) -> str:
    """Collapse a multi-line value into one line."""
    return re.sub(r"\s+", " ", text).strip()


def flatten(text: str) -> str:
    """One line from a field that may hold sub-bullets: list markers dropped, whitespace collapsed."""
    return one_line(" ".join(LIST_ITEM_RE.sub("", l) for l in text.splitlines()))


def plural(n: int, one: str, many: Optional[str] = None) -> str:
    return "%d %s" % (n, one if n == 1 else (many or one + "s"))


def mask_code(text: str) -> str:
    """Blank out the inside of `code spans`, keeping every offset, so regexes skip them."""
    return re.sub(r"`[^`]*`", lambda m: "`" + " " * (len(m.group(0)) - 2) + "`", text)


def strip_strike(text: str) -> str:
    """Remove ~~struck-through~~ text: it was superseded in generation 1."""
    return re.sub(r"~~.*?~~", "", text)


def shorten(text: str, width: int = 90) -> str:
    text = one_line(text)
    return text if len(text) <= width else text[: width - 1].rstrip() + "\u2026"


def strip_number(title: str) -> str:
    """'9. Plan' -> 'Plan', '§3 Environments' -> 'Environments'."""
    return re.sub(r"^(?:\u00a7\s*)?\d+(?:\.\d+)*\.?\s+", "", title).strip()


def display_heading(title: str) -> str:
    """Heading text as a reader would name it: no number, no '(required)'."""
    name = strip_number(title)
    return re.sub(r"\s*\((?:required|optional)[^)]*\)\s*$", "", name, flags=re.I).strip()


def heading_number(title: str) -> str:
    m = re.match(r"^(?:\u00a7\s*)?(\d+(?:\.\d+)*)\.?\s", title)
    return m.group(1) if m else ""


def dedent(lines: List[str]) -> List[str]:
    indents = [len(l) - len(l.lstrip()) for l in lines if l.strip()]
    cut = min(indents) if indents else 0
    return [l[cut:] if l.strip() else "" for l in lines]


def trim_blank(lines: List[str]) -> List[str]:
    """Drop leading and trailing blank lines and trailing horizontal rules."""
    lines = list(lines)
    while lines and (not lines[0].strip() or re.match(r"^\s*(?:---+|\*\*\*+)\s*$", lines[0])):
        lines.pop(0)
    while lines and (not lines[-1].strip() or re.match(r"^\s*(?:---+|\*\*\*+)\s*$", lines[-1])):
        lines.pop()
    return lines


def first_sentence(text: str) -> str:
    text = one_line(text)
    masked = mask_code(text)
    depth = 0
    for i, ch in enumerate(masked):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch in ".!?" and depth == 0 and i + 1 < len(masked) and masked[i + 1] == " ":
            nxt = masked[i + 2: i + 3]
            if nxt and (nxt.isupper() or nxt in "*`(\"'"):
                return text[: i + 1]
    return text


def split_sentences(line: str) -> List[str]:
    """Split one line into sentences at . ; ! ? outside parentheses and code spans."""
    masked = mask_code(line)
    out, start, depth, i = [], 0, 0, 0
    while i < len(masked):
        ch = masked[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch in ".;!?" and depth == 0:
            j = i + 1
            while j < len(masked) and masked[j] in "*_":
                j += 1
            if j == len(masked) or masked[j].isspace():
                piece = line[start:j].strip()
                if piece:
                    out.append(piece)
                start = j
                i = j
                continue
        i += 1
    piece = line[start:].strip()
    if piece:
        out.append(piece)
    return out


def ascii_fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def slugify(title: str) -> str:
    text = title
    previous = None
    while previous != text:  # nested parentheses
        previous = text
        text = re.sub(r"\([^()]*\)", " ", text)
    text = re.sub(r"[\u2019']s\b", "", text)
    text = ascii_fold(text).lower()
    words = [w for w in re.findall(r"[a-z0-9]+", text) if w not in STOP_WORDS][:MAX_SLUG_WORDS]
    while words and len("-".join(words)) > MAX_SLUG_CHARS:
        words.pop()
    return "-".join(words)


def yaml_scalar(value) -> str:
    if isinstance(value, int):
        return str(value)
    s = str(value)
    plain_ok = (
        s
        and s == s.strip()
        and s[0] not in "-?:,[]{}#&*!|>'\"%@`"
        and not re.search(r"[,\[\]{}#'\"]|: | #|:$", s)
        and s.lower() not in ("true", "false", "null", "yes", "no", "on", "off", "~")
        and not re.match(r"^[-+]?(\d[\d_]*)?(\.\d+)?([eE][-+]?\d+)?$", s)
    )
    if plain_ok:
        return s
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def yaml_list(values) -> str:
    return "[" + ", ".join(yaml_scalar(v) for v in values) + "]"


def normalise_blank_lines(lines: List[str]) -> str:
    out: List[str] = []
    for line in lines:
        line = line.rstrip()
        if not line and out and not out[-1]:
            continue
        out.append(line)
    while out and not out[-1]:
        out.pop()
    while out and not out[0]:
        out.pop(0)
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------------------------
# Markdown structure


@dataclass
class Section:
    index: int  # line of the heading
    level: int
    title: str
    end: int  # first line after the section

    @property
    def name(self) -> str:
        return strip_number(self.title)

    def body(self, lines: List[str]) -> List[str]:
        return lines[self.index + 1: self.end]


def iter_headings(lines: List[str], start: int = 0, end: Optional[int] = None) -> Iterator[Tuple[int, int, str]]:
    """Yield (line, level, text) for every ATX heading outside fenced code."""
    end = len(lines) if end is None else end
    fence = None
    for i in range(start, end):
        line = lines[i]
        m = FENCE_RE.match(line)
        if m:
            if fence is None:
                fence = m.group(1)
            elif line.strip().startswith(fence):
                fence = None
            continue
        if fence is not None:
            continue
        h = HEADING_RE.match(line)
        if h:
            yield i, len(h.group(1)), h.group(2)


def sections_at(lines: List[str], level: int) -> List[Section]:
    heads = list(iter_headings(lines))
    out = []
    for k, (i, lvl, text) in enumerate(heads):
        if lvl != level:
            continue
        end = next((j for (j, l2, _t) in heads[k + 1:] if l2 <= level), len(lines))
        out.append(Section(i, lvl, text, end))
    return out


def all_sections(lines: List[str]) -> List[Section]:
    heads = list(iter_headings(lines))
    out = []
    for k, (i, lvl, text) in enumerate(heads):
        end = next((j for (j, l2, _t) in heads[k + 1:] if l2 <= lvl), len(lines))
        out.append(Section(i, lvl, text, end))
    return out


def find_section(secs: List[Section], pred) -> Optional[Section]:
    return next((s for s in secs if pred(s.name)), None)


def is_summary(name: str) -> bool:
    return bool(re.search(r"\bsummary\b|\btl;?\s?dr\b", name, re.I))


def is_goals(name: str) -> bool:
    return bool(re.search(r"(?<![\w-])goals?\b", name, re.I))


def is_decisions(name: str) -> bool:
    return bool(re.search(r"\bdecisions?\b", name, re.I)) and not re.match(r"open\b", name, re.I)


def is_questions(name: str) -> bool:
    return bool(re.search(r"\bquestions?\b", name, re.I) or re.match(r"open decisions?\b", name, re.I))


def is_defaults(name: str) -> bool:
    return bool(re.search(r"\bdefaults?\b", name, re.I))


def is_plan(name: str) -> bool:
    return (bool(re.search(r"\bplan\b", name, re.I)) and not is_defaults(name)
            and not re.search(r"\bassum", name, re.I))


def is_plan_fallback(name: str) -> bool:
    return bool(re.search(r"\b(?:phases|rollout|sequencing|steps|waves|task list|order of work)\b", name, re.I))


def is_where(name: str) -> bool:
    return bool(re.search(r"\bwhere\s+(?:we|things)\b.*\b(?:are|stand)\b", name, re.I))


def is_shipped(name: str) -> bool:
    return bool(re.search(r"\bshipped\b", name, re.I))


def table_rows(body: List[str]) -> Tuple[Optional[str], List[str], bool]:
    """Return (first header row, data rows, whether there is non-table content)."""
    header, rows, other = None, [], False
    fence = None
    for idx, line in enumerate(body):
        s = line.strip()
        if FENCE_RE.match(line):
            fence = None if fence else "x"
            other = True
            continue
        if fence:
            continue
        if s.startswith("|"):
            nxt = body[idx + 1].strip() if idx + 1 < len(body) else ""
            if SEP_ROW_RE.match(s):
                continue
            if SEP_ROW_RE.match(nxt):
                header = header or s
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(not c for c in cells):
                continue
            rows.append(s)
        elif s and s not in ("\u2014", "-", "\u2013") and not re.match(r"^(?:---+|\*\*\*+)$", s):
            other = True
    return header, rows, other


def header_cells(row: str) -> List[str]:
    return [c.strip().lower() for c in row.strip().strip("|").split("|")]


# ---------------------------------------------------------------------------------------------
# Git, read-only and offline


class Git:
    def __init__(self, root: str):
        self.root = root
        self._main: Optional[str] = None
        self._main_done = False
        self._index: Optional[Dict[int, Tuple[str, bool]]] = None
        self._commits: Dict[str, bool] = {}
        self._slug: Optional[Tuple[Optional[str], Optional[str]]] = None

    def run(self, args: List[str]) -> Optional[str]:
        env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
        try:
            r = subprocess.run(["git", "-c", "core.quotepath=off", "-C", self.root] + args,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                               universal_newlines=True, encoding="utf-8", errors="replace")
        except OSError:
            return None
        return r.stdout if r.returncode == 0 else None

    def main_ref(self) -> Optional[str]:
        if not self._main_done:
            self._main_done = True
            for ref in ("origin/main", "main", "master"):
                if self.run(["rev-parse", "--verify", "--quiet", ref + "^{commit}"]) is not None:
                    self._main = ref
                    break
        return self._main

    def pr_index(self) -> Dict[int, Tuple[str, bool]]:
        """PR number -> (commit on main, whether it is a merge commit)."""
        if self._index is None:
            self._index = {}
            ref = self.main_ref()
            out = self.run(["log", ref, "--format=%H%x1f%P%x1f%s"]) if ref else None
            for line in (out or "").splitlines():
                parts = line.split("\x1f", 2)
                if len(parts) != 3:
                    continue
                sha, parents, subject = parts
                is_merge = len(parents.split()) > 1
                m = re.match(r"^Merge pull request #(\d+) ", subject)
                if not m:
                    m = re.search(r"\(#(\d+)\)\s*$", subject)
                if m:
                    self._index.setdefault(int(m.group(1)), (sha, is_merge))
        return self._index

    def pr_files(self, number: int) -> Optional[List[str]]:
        hit = self.pr_index().get(number)
        if not hit:
            return None
        sha, is_merge = hit
        if is_merge:
            out = self.run(["diff", "--name-only", sha + "^1", sha])
        else:
            out = self.run(["show", "--name-only", "--format=", sha])
        if out is None:
            return None
        return [l.strip() for l in out.splitlines() if l.strip()]

    def is_commit(self, sha: str) -> bool:
        if sha not in self._commits:
            self._commits[sha] = self.run(["cat-file", "-e", sha + "^{commit}"]) is not None
        return self._commits[sha]

    def remote_slug(self) -> Tuple[Optional[str], Optional[str]]:
        """(owner/repo, repo) of origin, as far as its URL tells."""
        if self._slug is None:
            url = (self.run(["remote", "get-url", "origin"]) or "").strip()
            owner_repo, repo = None, None
            m = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?/?$", url)
            if m and re.search(r"github|gitlab|bitbucket|@|://", url):
                owner_repo, repo = "%s/%s" % (m.group(1), m.group(2)), m.group(2)
            elif url:
                repo = re.sub(r"\.git$", "", os.path.basename(url.rstrip("/")))
            self._slug = (owner_repo, repo)
        return self._slug

    def is_this_repo(self, owner_repo: str) -> bool:
        full, name = self.remote_slug()
        if full:
            return owner_repo.lower() == full.lower()
        return bool(name) and owner_repo.split("/")[-1].lower() == name.lower()


# ---------------------------------------------------------------------------------------------
# LOOP.md


@dataclass
class LoopMd:
    path: str
    lines: List[str]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def section(self, pred, level: Optional[int] = None) -> Optional[Section]:
        secs = all_sections(self.lines)
        return next((s for s in secs if (level is None or s.level == level) and pred(s.name)), None)

    def proposals_folder(self) -> Optional[str]:
        sec = self.section(lambda n: bool(re.search(r"where things live", n, re.I)))
        lines = sec.body(self.lines) if sec else self.lines
        for line in lines:
            m = re.search(r"Proposals\W{0,4}\s*`([^`]+)`", line)
            if m:
                path = m.group(1).strip()
                if "<" in path or path.endswith(".md"):
                    path = os.path.dirname(path)
                return path.strip("/")
        return None

    def environments(self) -> Tuple[List[str], Optional[str], Optional[Section]]:
        """(environment names in table order, header row, section)."""
        sec = self.section(lambda n: bool(re.search(r"\benvironments?\b", n, re.I)), level=2)
        if not sec:
            return [], None, None
        header, rows, _other = table_rows(sec.body(self.lines))
        names = []
        for row in rows:
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            name = re.sub(r"[`*_]", "", cells[0]).strip().lower() if cells else ""
            if name:
                names.append(name)
        return names, header, sec


def read_lines(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read().splitlines()


def loop_md_checklist(loop: Optional[LoopMd]) -> List[str]:
    if loop is None:
        return ["There is no LOOP.md. Run /loop-init to write one (generation 2)."]
    items = []
    lines = loop.lines

    def where(sec: Optional[Section], fallback: str) -> str:
        if not sec:
            return fallback
        num = heading_number(sec.title)
        return ("\u00a7%s %s" % (num, display_heading(sec.title))) if num else display_heading(sec.title)

    conventions = loop.section(lambda n: bool(re.search(r"\bconventions\b", n, re.I)), level=2)
    conv = where(conventions, "Conventions")
    for i, line in enumerate(lines):
        if re.match(r"^\s*\|\s*Proposed\s*\|", line):
            items.append("%s: remove the generation 1 proposal Status table (its `| Proposed |` row is "
                         "line %d). Status is derived now, never written." % (conv, i + 1))
            break
    for i, line in enumerate(lines):
        if "Plan step status" in line:
            items.append("%s: remove the \"Plan step status\" convention (line %d)." % (conv, i + 1))
            break
    if "Concern:" not in loop.text:
        items.append("%s: add the concern conventions: branches `<loop>/<concern>`, the `Concern:` "
                     "trailer, code and loop documents in separate PRs, evidence lines, no status lines."
                     % conv)
    live = loop.section(lambda n: bool(re.search(r"where things live", n, re.I)), level=2)
    if live is None:
        items.append("Add a \"Where things live\" section that names `docs/loops/`.")
    elif "docs/loops" not in "\n".join(live.body(lines)):
        items.append("%s: add the Loops line: `docs/loops/<loop>/README.md`, plus one `<concern>.md` per "
                     "concern; the loop skills track every folder there." % where(live, ""))
    deleg = loop.section(lambda n: bool(re.search(r"\bdelegated\b", n, re.I)))
    if deleg is None or not re.search(r"loop-document|docs/loops", "\n".join(deleg.body(lines))):
        items.append("%s: add the default row that lets agents merge loop-document PRs (base `main`, "
                     "files only under `docs/loops/`, cited commits already on `main`, checked by "
                     "`check_loop_pr.sh`)." % where(deleg, "\u00a72.1 Delegated actions"))
    names, header, env_sec = loop.environments()
    env_where = where(env_sec, "\u00a73 Environments")
    if env_sec is None:
        items.append("Add an Environments table with, for each environment, a command that prints the "
                     "commit it serves.")
    else:
        body = "\n".join(env_sec.body(lines))
        if not header or not re.search(r"served commit", header, re.I):
            gen1 = ""
            if header and re.search(r"deployed version", header, re.I):
                gen1 = " The generation 1 \"Deployed version: how to see it\" column is a starting point."
            items.append("%s: add the \"Served commit: a command that prints its SHA\" column, and fill "
                         "it for every environment agents may read.%s" % (env_where, gen1))
        if re.search(r"<(?:command|host|endpoint)[^>]*>", body):
            items.append("%s: fill the `<command>` placeholders." % env_where)
    return items


def old_skills(root: str) -> List[str]:
    bases = [os.path.join(os.path.expanduser("~"), ".claude", "skills"), os.path.join(root, ".claude", "skills")]
    found = []
    for base in bases:
        for name in RETIRED_SKILLS:
            path = os.path.join(base, name, "SKILL.md")
            if os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as fh:
                        text = fh.read()
                except OSError:
                    continue
                if RETIRED_MARK not in text:
                    found.append(os.path.dirname(path))
    return found


# ---------------------------------------------------------------------------------------------
# Proposals and steps


@dataclass
class Warning_:
    kind: str
    text: str


@dataclass
class Step:
    kind: str
    id: str
    title: str
    level: int
    line: int  # 0-based heading line
    fields: List[Tuple[str, str, List[str]]] = field(default_factory=list)  # (name, label, lines)
    body: List[str] = field(default_factory=list)
    loose_status: Optional[str] = None
    parent: Optional["Step"] = None
    children: List["Step"] = field(default_factory=list)
    container: bool = False
    # Results
    done: bool = False
    reason: str = ""
    migrate: bool = False
    slug: str = ""
    needs: List[str] = field(default_factory=list)
    needs_dropped: List[str] = field(default_factory=list)
    prs: List[str] = field(default_factory=list)
    touches: List[str] = field(default_factory=list)
    effects: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    evidence_paragraph: Optional[List[str]] = None
    evidence_no_sha: int = 0
    evidence_foreign_sha: int = 0
    evidence_inherited: int = 0

    @property
    def label(self) -> str:
        return "%s %s" % (self.kind, self.id)

    def get(self, name: str) -> Optional[List[str]]:
        for n, _label, lines in self.fields:
            if n == name:
                return lines
        return None

    def text(self, name: str) -> str:
        lines = self.get(name)
        return "\n".join(lines) if lines else ""

    def labels(self) -> str:
        return " ".join(label for _n, label, _l in self.fields)

    @property
    def status(self) -> str:
        if self.get("status") is not None:
            return flatten(self.text("status"))
        return one_line(self.loose_status or "")


@dataclass
class Proposal:
    path: str
    rel: str
    slug: str
    lines: List[str]
    state: str
    status_date: str
    status_index: int
    title: str = ""
    action: str = ""  # migrate | history | already | not-selected
    why: str = ""
    steps: List[Step] = field(default_factory=list)
    plan_name: Optional[str] = None
    warnings: List[Warning_] = field(default_factory=list)
    files: Dict[str, str] = field(default_factory=dict)  # repo-relative path -> content
    mark: Optional[str] = None  # new content for the history file
    mark_state: str = ""  # "add" | "present" | "off"
    readme_stats: Dict[str, object] = field(default_factory=dict)

    def warn(self, kind: str, text: str) -> None:
        self.warnings.append(Warning_(kind, text))

    @property
    def leaf_steps(self) -> List[Step]:
        return [s for s in self.steps if not s.container]


def read_proposal(path: str, rel: str) -> Optional[Proposal]:
    lines = read_lines(path)
    fence = None
    for i, line in enumerate(lines):
        if FENCE_RE.match(line):
            fence = None if fence else "x"
            continue
        if fence:
            continue
        m = STATUS_LINE_RE.match(line)
        if m:
            slug = os.path.splitext(os.path.basename(path))[0]
            p = Proposal(path, rel, slug, lines, one_line(m.group("state")), m.group("date"), i)
            heading = next((t for (_i, lvl, t) in iter_headings(lines) if lvl == 1), slug)
            p.title = re.sub(r"^(?:Proposal|RFC)\s*[:\u2014\u2013-]\s*", "", heading, flags=re.I).strip()
            return p
    return None


def parse_step_body(step: Step, body: List[str]) -> None:
    current: Optional[List[str]] = None
    prev_blank = False
    fence = None
    for line in body:
        if fence is None:
            m = FIELD_RE.match(line)
            if m:
                name = (m.group("n1") or m.group("n2")).lower()
                label = (m.group("l1") or m.group("l2") or "").strip()
                current = [m.group("rest").rstrip()]
                step.fields.append((name, label, current))
                prev_blank = False
                continue
            if HEADING_RE.match(line):
                current = None
                step.body.append(line)
                continue
        if FENCE_RE.match(line):
            fence = None if fence else "x"
        if current is not None:
            if not line.strip():
                current.append("")
                prev_blank = True
                continue
            if prev_blank and fence is None and not line[:1].isspace() and not FENCE_RE.match(line):
                current = None
                step.body.append(line)
                prev_blank = False
                continue
            current.append(line.rstrip())
            prev_blank = False
        else:
            step.body.append(line)
    for _n, _l, lines in step.fields:
        while lines and not lines[-1].strip():
            lines.pop()
    if step.get("status") is None:
        for line in step.body:
            m = LOOSE_STATUS_RE.match(line)
            if m:
                step.loose_status = (m.group("extra").strip() + ": " if m.group("extra").strip() else "") + m.group("rest")
                step.body = [l for l in step.body if l is not line]
                break


def parse_plan(p: Proposal) -> None:
    secs = sections_at(p.lines, 2)
    plan = find_section(secs, is_plan) or find_section(secs, is_plan_fallback)
    if plan is None:
        p.warn("no plan", "no Plan section (a `##` heading naming the plan), so no steps")
        return
    p.plan_name = display_heading(plan.title)
    heads = list(iter_headings(p.lines, plan.index + 1, plan.end))
    steps: List[Step] = []
    marks: List[Tuple[int, Optional[Step]]] = []  # heads index -> step or None
    for k, (i, lvl, text) in enumerate(heads):
        clean = re.sub(r"^[*_~]+|[*_~]+$", "", text).strip()
        m = STEP_HEADING_RE.match(clean) if lvl in (3, 4) else None
        if m:
            title = (m.group("title") or "").strip() or "%s %s" % (m.group("kind"), m.group("id"))
            st = Step(m.group("kind"), m.group("id"), title, lvl, i)
            steps.append(st)
            marks.append((k, st))
        else:
            marks.append((k, None))
    # Body of each step, and the headings no step owns.
    owner: Optional[Step] = None
    for k, (i, lvl, text) in enumerate(heads):
        st = marks[k][1]
        if st is not None:
            end = plan.end
            for (j, l2, _t), (_k2, st2) in zip(heads[k + 1:], marks[k + 1:]):
                if l2 <= lvl or st2 is not None:
                    end = j
                    break
            parse_step_body(st, p.lines[i + 1: end])
            owner = st
            continue
        if owner is not None and lvl > owner.level and owner.line < i:
            # A sub-heading inside a step stays part of that step.
            continue
        owner = None
        if lvl in (3, 4):
            p.warn("ignored heading", "\"%s %s\" (line %d) in \"%s\" is not a step" % ("#" * lvl, text, i + 1, p.plan_name))
    # Containers: a step with deeper step children and no Status of its own.
    for idx, st in enumerate(steps):
        kids = []
        for other in steps[idx + 1:]:
            if other.level <= st.level:
                break
            kids.append(other)
        if kids and st.get("status") is None and not st.loose_status:
            st.container = True
            st.children = kids
            for kid in kids:
                kid.parent = st
    p.steps = steps
    if not steps:
        p.warn("no steps", "no `Step`, `Phase` or `Wave` headings in \"%s\", so the loop has no concerns yet; "
                           "cut them with /loop-design %s" % (p.plan_name, p.slug))


def classify(step: Step, top: str) -> Tuple[bool, str]:
    status = step.status
    if not status:
        return False, "unfinished: no Status field"
    if re.match(r"(?i)\s*done\b", status):
        # "done for the web; the app waits" is half done: keep it tracked, as a concern.
        partial = re.match(r"(?i)\s*done\s+for\b[^,;.(]*", status)
        if partial:
            return False, "unfinished: Status says \"%s\", which is only part of it" % partial.group(0).strip()
        marker = UNFINISHED_RE.search(mask_code(status))
        if marker and not re.search(r"(?i)\baccepted\b", status):
            return False, ("unfinished: Status starts with \"done\", but also says \"%s\""
                           % status[marker.start(): marker.end()])
        if marker:
            return True, "done: Status starts with \"done\", and the owner accepted what is left as gaps"
        return True, "done: Status starts with \"done\""
    lines = [l for l in (step.get("status") or []) if l.strip()]
    if len(lines) > 1:
        last = re.sub(r"[*_]", "", LIST_ITEM_RE.sub("", lines[-1])).strip()
        last_body = re.sub(r"^(?:Step|Phase|Wave)\s+\S+?\s*[:\u2014\u2013-]\s*", "", last, flags=re.I)
        if re.match(r"(?i)done\b", last_body):
            return True, "done: the Status's last line says \"%s\"" % shorten(last, 60)
    masked = mask_code(status)
    t = re.escape(top)
    neg = re.search(r"(?i)\bnot\s+(?:yet\s+)?on\s+%s\b" % t, masked)
    if neg:
        return False, "unfinished: Status says \"%s\"" % status[neg.start(): neg.end()]
    pieces, start = [], 0
    for m in re.finditer(r";|\.\s", masked):
        pieces.append((start, m.start()))
        start = m.end()
    pieces.append((start, len(masked)))
    on_top = None
    for idx, (a, b) in enumerate(pieces):
        if re.search(r"(?i)\bon\b[^.;]*\b%s\b" % t, masked[a:b]):
            if re.search(r"(?i)\bverified\b", masked[a:]):
                on_top = status[a:b].strip()
                break
    if on_top is None:
        if re.search(r"(?i)\bon\b[^.;]*\b%s\b" % t, masked):
            return False, "unfinished: on %s, but not verified there" % top
        return False, "unfinished: Status \"%s\"" % shorten(status, 70)
    marker = UNFINISHED_RE.search(masked)
    if marker:
        return False, ("unfinished: on %s and verified, but the Status also says \"%s\""
                       % (top, status[marker.start(): marker.end()]))
    return True, "done: on %s and verified (\"%s\")" % (top, shorten(on_top, 60))


def find_prs(text: str, git: Git) -> List[str]:
    out: List[str] = []
    prev_repo, prev_end = None, -1
    for m in PR_RE.finditer(text):
        repo = m.group("repo")
        if not repo and prev_repo and re.match(r"^\s*(?:,|and|&|,\s*and)\s*$", text[prev_end: m.start()]):
            repo = prev_repo
        if repo and git.is_this_repo(repo):
            ref = m.group("num")
            prev_repo = None if not m.group("repo") else repo
        elif repo:
            ref = "%s#%s" % (repo, m.group("num"))
            prev_repo = repo
        else:
            ref = m.group("num")
            prev_repo = None
        prev_end = m.end()
        if ref not in out:
            out.append(ref)
    return out


def collapse_touches(files: List[str], protected: Tuple[str, ...] = (LOOPS_REL,)) -> List[str]:
    """At most MAX_TOUCHES files are listed; more collapse to `<dir>/**`, one per directory.

    A glob never covers a protected folder (docs/loops/, the proposals folder): status reads
    `git log -- <touches>` to tell whether a proof went stale, and loop documents change all the
    time. Files directly in an ancestor of a protected folder (docs/api.md) stay as files.
    """
    files = list(dict.fromkeys(files))
    if len(files) <= MAX_TOUCHES:
        return files
    shielded = set()
    for path in protected:
        parts = path.strip("/").split("/")
        shielded.update("/".join(parts[: i + 1]) for i in range(len(parts)))

    def glob_for(directory: str) -> Optional[str]:
        return None if (not directory or directory in shielded) else directory + "/**"

    def depth(entry: str) -> int:
        return entry.count("/") if entry.endswith("/**") else 0

    def covered(entries: List[str]) -> List[str]:
        globs = [e[:-2] for e in entries if e.endswith("/**")]
        keep = [e for e in entries
                if not any((e[:-2] if e.endswith("/**") else e) != g and (e[:-2] if e.endswith("/**") else e).startswith(g)
                           for g in globs)]
        return list(dict.fromkeys(keep))

    entries = covered([glob_for(os.path.dirname(f)) or f for f in files])
    while len(entries) > MAX_TOUCHES:
        deepest = max(depth(e) for e in entries)
        if deepest <= 1:
            break
        changed = False
        nxt = []
        for e in entries:
            if e.endswith("/**") and depth(e) == deepest:
                parent = glob_for(e[:-3].rsplit("/", 1)[0])
                if parent:
                    nxt.append(parent)
                    changed = True
                    continue
            nxt.append(e)
        if not changed:
            break
        entries = covered(nxt)
    return entries


def step_refs(text: str) -> List[str]:
    ids: List[str] = []
    for m in STEP_REF_RE.finditer(text):
        raw = m.group("ids")
        for a, b in re.findall(r"(\d+)\s*[\u2013\u2014-]\s*(\d+)\b", raw):
            if int(b) - int(a) < 50:
                ids.extend(str(n) for n in range(int(a), int(b) + 1))
        raw = re.sub(r"(\d+)\s*[\u2013\u2014-]\s*(\d+)\b", " ", raw)
        ids.extend(re.findall(r"\d+[a-z]?|\b[A-Z]\b", raw))
    return list(dict.fromkeys(ids))


# ---------------------------------------------------------------------------------------------
# Evidence


def pick_sha(text: str, git: Git) -> Tuple[Optional[str], bool]:
    """(sha, whether it is a commit in this repository)."""
    candidates = [m.group(1) for m in BACKTICK_HEX_RE.finditer(text)]
    candidates += [m.group(0) for m in HEX_TOKEN_RE.finditer(text)]
    candidates = [c for c in dict.fromkeys(candidates)
                  if re.search(r"\d", c) and re.search(r"[a-f]", c)]
    for c in candidates:
        if git.is_commit(c):
            return c, True
    return (candidates[0], False) if candidates else (None, False)


def env_in(text: str, envs: List[str]) -> Optional[str]:
    best = None
    for env in envs:
        m = re.search(r"(?i)(?<![\w-])%s(?![\w-])" % re.escape(env), text)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), env)
    return best[1] if best else None


def clean_metadata(inner: str, envs: List[str]) -> str:
    inner = RUNG_RE.sub("", inner)
    inner = re.sub(r"^\s*:\s*", "", inner)
    inner = DATE_EXT_RE.sub("", inner)
    inner = BACKTICK_HEX_RE.sub("", inner)
    for env in envs:
        inner = re.sub(r"(?i)(^|[,;])\s*%s\s*(?=[,;]|$)" % re.escape(env), r"\1", inner)
    inner = re.sub(r"\s*([,;:])\s*(?:[,;:]\s*)+", r"\1 ", inner)
    return inner.strip(" ,;:")


def parse_proof(proof_fields: List[Tuple[str, List[str]]], envs: List[str], status_date: str,
                git: Git, step: Step) -> None:
    """Fill step.evidence (lines) and step.evidence_paragraph (unparsed text) from the Proof fields.

    Each sentence that names one verdict starts a unit, and the sentences after it, up to the next
    verdict, belong to it. A sentence naming two different verdicts ("partly HOLDS, partly UNPROVEN")
    is a summary, kept as context. HOLDS needs its own commit to count. An UNPROVEN or CONTRADICTS
    without one takes the commit and environment of the verdict before it in the same field, so a
    partial HOLDS never outlives the gap the same proof reports.
    """
    verbatim: List[List[str]] = []
    last_date = None
    for label, lines in proof_fields:
        text = "\n".join(lines).strip()
        if not text or one_line(text) in ("—", "-", "–", "n/a", "none"):
            continue
        label_date = DATE_RE.search(label)
        label_rung = RUNG_RE.search(label)
        label_env = env_in(label, envs)
        label_sha, label_sha_here = pick_sha(label, git)
        sentences: List[str] = []
        for raw in lines:
            line = LIST_ITEM_RE.sub("", strip_strike(raw)).strip()
            if line:
                sentences.extend(split_sentences(line))
        units: List[List[str]] = []
        preamble: List[str] = []
        for s in sentences:
            found = set(VERDICT_RE.findall(s))
            if len(found) == 1:
                units.append([s])
            elif units:
                units[-1].append(s)
            else:
                preamble.append(s)
        if not units:
            verbatim.append(dedent([lines[0].strip()] + lines[1:]))
            continue
        for d in DATE_RE.findall(" ".join(preamble)):
            last_date = d
        if label_date and not last_date:
            last_date = label_date.group(0)
        anchor: Optional[Tuple[str, bool, str]] = None  # (sha, in this repo, env) of the last bound verdict
        for unit in units:
            first, whole = unit[0], " ".join(unit)
            vm = VERDICT_RE.search(first)
            verdict = vm.group(1)
            subject = re.sub(r"[*_~\s]+", " ", first[: vm.start()]).strip()
            subject = re.sub(r"(?i)^proof\s*:\s*", "", subject).strip(" :")
            after = first[vm.end():]
            dm = DATE_RE.search(whole)
            date = dm.group(0) if dm else (last_date or status_date)
            rm = RUNG_RE.search(first) or RUNG_RE.search(whole) or label_rung
            rung = rm.group(1) if rm else "?"
            sha, here = pick_sha(first, git)
            if not sha:
                sha, here = pick_sha(whole, git)
            if not sha and label_sha:
                sha, here = label_sha, label_sha_here
            env = None
            em = re.match(r"^[*_\s]*on\s+(?:the\s+)?([A-Za-z][\w-]*)", after)
            if em and em.group(1).lower() in envs:
                env = em.group(1).lower()
            paren = re.match(r"^([^():]{0,80}?)\s*\(([^()]*)\)", after)
            if not env and paren:
                env = env_in(paren.group(2), envs)
            if not env:
                env = env_in(subject, envs) or label_env
            if not env and envs:
                om = re.search(r"(?i)\bon\s+(?:the\s+)?(%s)\b" % "|".join(re.escape(e) for e in envs), after)
                env = om.group(1).lower() if om else None
            if not env:
                env = env_in(after, envs)
            inherited = False
            if not sha and verdict != "HOLDS" and anchor and env in (None, anchor[2]):
                sha, here, env = anchor[0], anchor[1], anchor[2]
                inherited = True
            env = env or "unknown"
            if sha and not inherited:
                anchor = (sha, here, env)
            # The rest of the text, without the metadata the line already carries.
            if subject:
                rest = whole
            else:
                r = after
                if em and em.group(1).lower() == env:
                    r = r[em.end():]
                pm = re.match(r"^([^():]{0,80}?)\s*\(([^()]*)\)", r)
                if pm and (RUNG_RE.search(pm.group(2)) or DATE_RE.search(pm.group(2))
                           or BACKTICK_HEX_RE.search(pm.group(2)) or env_in(pm.group(2), envs)):
                    left = clean_metadata(pm.group(2), envs)
                    r = pm.group(1) + ((" (%s)" % left) if left else "") + r[pm.end():]
                rest = (r + " " + " ".join(unit[1:])).strip()
                rest = re.sub(r"^[\s*_,:;.—–-]+", "", rest)
            rest = one_line(rest.replace("**", ""))
            if not rest:
                rest = one_line(first.replace("**", ""))
            line = "- %s · C1 · %s · rung %s · %s @%s · %s" % (
                date, verdict, rung, env, sha or "?", rest)
            if not sha:
                line += " (migrated without a commit, so status does not count it)"
                step.evidence_no_sha += 1
            else:
                if inherited:
                    line += " (commit and environment from the verdict before it)"
                    step.evidence_inherited += 1
                if not here:
                    step.evidence_foreign_sha += 1
            step.evidence.append(line)
            for d in DATE_RE.findall(whole):
                last_date = d
    if verbatim:
        step.evidence_paragraph = [l for block in verbatim for l in (block + [""])]
        while step.evidence_paragraph and not step.evidence_paragraph[-1]:
            step.evidence_paragraph.pop()


# ---------------------------------------------------------------------------------------------
# Planning one proposal


@dataclass
class Context:
    root: str
    proposals_rel: str
    today: str
    top: str
    envs: List[str]
    include_done: bool
    mark: bool
    git: Git


def plan_proposal(p: Proposal, ctx: Context) -> None:
    secs = sections_at(p.lines, 2)
    loop_rel = "%s/%s" % (LOOPS_REL, p.slug)
    parse_plan(p)
    decisions_sec = find_section(secs, is_decisions)
    dec_header, dec_rows, dec_other = table_rows(decisions_sec.body(p.lines)) if decisions_sec else (None, [], False)
    decision_ids = set()
    for row in dec_rows:
        m = re.match(r"^\|\s*(?:~~)?\s*D(\d+)\b", row)
        if m:
            decision_ids.add(m.group(1))

    for st in p.leaf_steps:
        st.done, st.reason = classify(st, ctx.top)
        st.migrate = (not st.done) or ctx.include_done
    for st in p.steps:
        if st.container:
            st.reason = "container for %s" % ", ".join(k.id for k in st.children)

    # Concern slugs, unique within the loop.
    used = set()
    for st in p.leaf_steps:
        if not st.migrate:
            continue
        base = slugify(st.title)
        if not base or base == "readme":
            base = "%s-%s" % (st.kind.lower(), st.id.lower())
        slug, n = base, 2
        while slug in used:
            slug = "%s-%d" % (base, n)
            n += 1
        used.add(slug)
        st.slug = slug

    by_id: Dict[str, List[Step]] = {}
    for st in p.steps:
        by_id.setdefault(st.id, []).append(st)

    for st in p.leaf_steps:
        if not st.migrate:
            continue
        # needs
        heading_text = st.title + " " + st.labels()
        if st.parent:
            heading_text += " " + st.parent.title
        refs = step_refs(" ".join([heading_text, st.text("does"), st.text("gate")]))
        for ref in refs:
            targets = by_id.get(ref)
            if not targets:
                st.needs_dropped.append("Step %s, not in this plan" % ref)
                continue
            for target in targets:
                for t in (target.children if target.container else [target]):
                    if t is st:
                        continue
                    if t.migrate:
                        if t.slug not in st.needs:
                            st.needs.append(t.slug)
                    else:
                        st.needs_dropped.append("%s, done and kept as history" % t.label)
        for num in dict.fromkeys(DECISION_REF_RE.findall(heading_text)):
            if decision_ids and num not in decision_ids:
                st.needs_dropped.append("D%s, not in the Decisions table" % num)
                continue
            ref = "%s/D%s" % (p.slug, num)
            if ref not in st.needs:
                st.needs.append(ref)
        # prs and touches
        proofs = [(label, lines) for (name, label, lines) in st.fields if name == "proof"]
        pr_text = st.status + "\n" + "\n".join(label + " " + "\n".join(lines) for label, lines in proofs)
        st.prs = find_prs(pr_text, ctx.git)
        files: List[str] = []
        proposals_prefix = ctx.proposals_rel.rstrip("/") + "/"
        for ref in st.prs:
            if not ref.isdigit():
                continue
            got = ctx.git.pr_files(int(ref))
            if got is None:
                continue
            for f in got:
                if f.startswith(proposals_prefix) or f.startswith(LOOPS_REL + "/"):
                    continue
                files.append(f)
        st.touches = sorted(collapse_touches(files, (LOOPS_REL, ctx.proposals_rel.strip("/"))),
                            key=lambda e: (e.lower(), e))
        # effects
        gate = one_line(st.text("gate").replace("**", ""))
        st.effects = [] if (not gate or re.match(r"(?i)none\b", gate)) else [gate]
        # evidence
        parse_proof(proofs, ctx.envs, p.status_date, ctx.git, st)
        if st.evidence_paragraph:
            if st.evidence:
                p.warn("unparsed proof", "%s: part of its Proof has no HOLDS, CONTRADICTS or UNPROVEN; kept verbatim, "
                                         "not counted by status" % st.label)
            else:
                p.warn("unparsed proof", "%s: its Proof has no HOLDS, CONTRADICTS or UNPROVEN; kept verbatim, not "
                                         "counted by status" % st.label)
        if not st.fields:
            p.warn("no fields", "%s has none of the generation 1 fields (Does, Done when, Gate, Status, Proof): "
                                "its text became the Approach, and C1 is a TODO for the owner" % st.label)
        elif st.get("done when") is None or not one_line(st.text("done when")):
            p.warn("no done-when", "%s: no \"Done when\"; C1 is a TODO for the owner" % st.label)

    if p.steps and not any(s.migrate for s in p.leaf_steps):
        p.warn("all steps done", "every step is done, so the loop has no concerns; check whether the proposal "
                                 "itself is done (its Status says %s)" % p.state)

    readme = render_readme(p, ctx, secs, decisions_sec, dec_header, dec_rows, dec_other)
    p.files["%s/README.md" % loop_rel] = readme
    for st in p.leaf_steps:
        if st.migrate:
            p.files["%s/%s.md" % (loop_rel, st.slug)] = render_concern(p, st, ctx)

    # The history marker.
    if not ctx.mark:
        p.mark_state = "off"
    elif any(MIGRATED_LINE_RE.match(l) for l in p.lines[: p.status_index + 40]):
        p.mark_state = "present"
    else:
        p.mark_state = "add"
        p.mark = mark_history(p, ctx)


def rel_link(target_rel: str, from_dir_rel: str, root: str) -> str:
    rel = os.path.relpath(os.path.join(root, target_rel), os.path.join(root, from_dir_rel))
    return rel.replace(os.sep, "/")


def render_readme(p: Proposal, ctx: Context, secs: List[Section], decisions_sec: Optional[Section],
                  dec_header: Optional[str], dec_rows: List[str], dec_other: bool) -> str:
    loop_rel = "%s/%s" % (LOOPS_REL, p.slug)
    link = rel_link(p.rel, loop_rel, ctx.root)
    out = ["# %s" % p.title, ""]
    if not p.steps:
        tail = ("Its plan has no steps in generation 1 form, so this loop has no concerns yet: cut them with "
                "/loop-design %s." % p.slug)
    elif not any(s.migrate for s in p.leaf_steps):
        tail = "Every step in it was done, so this loop has no concerns yet."
    else:
        tail = "Done steps stay there; unfinished steps became the concerns in this folder."
    out += ["> Migrated from [`%s`](%s) on %s by %s. That file is now history. %s"
            % (p.rel, link, ctx.today, TOOL, tail), ""]

    # Intent and non-goals.
    summary = find_section(secs, is_summary)
    intent = trim_blank(summary.body(p.lines)) if summary else []
    if not intent:
        p.warn("no summary", "no Summary section; the README's Intent is a TODO for the owner")
        intent = ["TODO(owner): the history file has no Summary section. State the intent in /loop-design %s."
                  % p.slug]
    if re.match(r"^\s*(?:\||#|```|~~~|>)", intent[0]):
        intent_lines = ["**Intent.**", ""] + intent
    else:
        intent_lines = ["**Intent.** " + intent[0].strip()] + intent[1:]
    goals_sec = find_section(secs, is_goals)
    goals_body = goals_sec.body(p.lines) if goals_sec else []
    non_goals = extract_non_goals(goals_body)
    if not non_goals:
        ng_sec = find_section(secs, lambda n: bool(re.match(r"non-goals\b", n, re.I)))
        ng_body = trim_blank(ng_sec.body(p.lines)) if ng_sec else []
        if ng_body and LIST_ITEM_RE.match(ng_body[0]):
            non_goals = [""] + ng_body  # a list may follow the label directly
        elif ng_body and re.match(r"^\s*(?:\||#|```|~~~|>)", ng_body[0]):
            non_goals = ["", ""] + ng_body  # other blocks need a blank line after the label
        elif ng_body:
            non_goals = ng_body
    if non_goals:
        non_goal_lines = [("**Non-goals.** " + non_goals[0]).rstrip()] + non_goals[1:]
    else:
        non_goal_lines = ["**Non-goals.** \u2014"]
    out += intent_lines
    if len(intent_lines) > 1:
        out.append("")
    out += non_goal_lines + [""]

    goals = extract_goals(goals_body)
    p.readme_stats["goals"] = len(goals)
    if goals_sec and not goals:
        p.warn("not a table", "\"%s\" has no `- **G1**` goal bullets; goals left in the history file"
               % display_heading(goals_sec.title))
    out += ["## Goals", ""]
    for g in goals:
        out += g
    out += [""]

    out += ["## Relations", "",
            "- Not compared with other loops yet. Run /loop-design %s to record relations." % p.slug, ""]

    where = find_section(secs, is_where)
    if where:
        pointer = ("See the history file's \"%s\" section, as of %s. Verify before relying on it."
                   % (display_heading(where.title), p.status_date))
    else:
        pointer = "See the history file, as of %s. Verify before relying on it." % p.status_date
    out += ["## Where we are", "", pointer, ""]

    out += ["## Shared decisions", "", DECISIONS_HEADER, TABLE_SEP] + dec_rows
    p.readme_stats["decisions"] = len(dec_rows)
    if decisions_sec and dec_header and header_cells(dec_header) != header_cells(DECISIONS_HEADER):
        p.warn("table columns differ", "the Decisions table's columns are \"%s\", not the generation 2 ones; rows "
                                       "copied as they are" % dec_header.strip())
    if decisions_sec and not dec_rows and dec_other:
        p.warn("not a table", "\"%s\" is not a table; its decisions stay in the history file, unnumbered"
               % display_heading(decisions_sec.title))
    defaults = find_section(secs, is_defaults)
    defaults_body = trim_blank(defaults.body(p.lines)) if defaults else []
    p.readme_stats["defaults"] = bool(defaults_body)
    if defaults_body:
        out += ["", "### Defaults this loop assumes (veto any)", ""] + defaults_body
    out += [""]

    questions = find_section(secs, is_questions)
    q_header, q_rows, q_other = table_rows(questions.body(p.lines)) if questions else (None, [], False)
    p.readme_stats["questions"] = len(q_rows)
    if questions and q_header and header_cells(q_header) != header_cells(QUESTIONS_HEADER):
        p.warn("table columns differ", "the Questions table's columns are \"%s\", not the generation 2 ones; rows "
                                       "copied as they are" % q_header.strip())
    if questions and not q_rows and q_other:
        p.warn("not a table", "\"%s\" is not a table; its questions stay in the history file, unnumbered"
               % display_heading(questions.title))
    out += ["## Questions", "", QUESTIONS_HEADER, TABLE_SEP] + q_rows + [""]

    out += ["## Evidence", ""]

    shipped = find_section(secs, is_shipped)
    if shipped:
        line = ("What shipped before the migration is in the history file's \"%s\" section."
                % display_heading(shipped.title))
    else:
        line = "What shipped before the migration is recorded in the history file."
    out += ["## Shipped", "", line]
    done = [s for s in p.leaf_steps if s.done and not s.migrate]
    p.readme_stats["shipped"] = len(done)
    if done:
        out.append("")
        for s in done:
            out.append("- %s, %s: %s" % (s.label, s.title, first_sentence(s.status)))
    return normalise_blank_lines(out)


def extract_goals(body: List[str]) -> List[List[str]]:
    goals, i, n = [], 0, len(body)
    while i < n:
        if not GOAL_RE.match(body[i]):
            i += 1
            continue
        block, j = [body[i].rstrip()], i + 1
        while j < n:
            line = body[j]
            if not line.strip():
                k = j
                while k < n and not body[k].strip():
                    k += 1
                if k < n and body[k][:1].isspace():
                    block += [""] * (k - j)
                    j = k
                    continue
                break
            if not line[:1].isspace():
                break
            block.append(line.rstrip())
            j += 1
        goals.append(block)
        i = j
    return goals


def extract_non_goals(body: List[str]) -> List[str]:
    for idx, line in enumerate(body):
        m = re.match(r"^\s*(?:\*\*)?Non-goals\b(?P<after>.*)$", line, re.I)
        if not m:
            continue
        first = re.sub(r"^[\s:.,*]+", "", m.group("after")).strip()
        out = [first]
        j = idx + 1
        while j < len(body):
            l = body[j]
            if not l.strip():
                k = j
                while k < len(body) and not body[k].strip():
                    k += 1
                if k < len(body) and (body[k][:1].isspace() or LIST_ITEM_RE.match(body[k])) and not GOAL_RE.match(body[k]):
                    out += [""] * (k - j)
                    j = k
                    continue
                break
            if HEADING_RE.match(l) or GOAL_RE.match(l):
                break
            out.append(l.rstrip())
            j += 1
        more = trim_blank(out[1:])
        return [first] + more if (first or more) else []
    return []


def render_concern(p: Proposal, st: Step, ctx: Context) -> str:
    loop_rel = "%s/%s" % (LOOPS_REL, p.slug)
    link = rel_link(p.rel, loop_rel, ctx.root)
    fm = ["---",
          "needs: %s" % yaml_list(st.needs),
          "touches: %s" % yaml_list(st.touches),
          "effects: %s" % yaml_list(st.effects),
          "ships-to: %s" % yaml_scalar(ctx.top)]
    if st.prs:
        fm.append("prs: %s" % yaml_list([int(r) if r.isdigit() else r for r in st.prs]))
    fm.append("---")
    status = st.status or "no status recorded"
    out = fm + ["# %s" % st.title, "",
                "> Migrated from [`%s`](%s) %s on %s; its status then: \"%s\". Rewrite the title as an outcome "
                "in /loop-design." % (p.rel, link, st.label, ctx.today, status), ""]
    out += ["## Done when", ""]
    done_when = st.get("done when")
    if done_when and one_line("\n".join(done_when)):
        first = done_when[0].strip()
        rest = ["  " + l if l else "" for l in dedent(done_when[1:])]
        out += [("- **C1** " + first).rstrip()] + rest
    else:
        out += ["- **C1** TODO(owner): this step had no \"done when\"."]
    out += ["", "## Design", "", "### Where we are", "", "### Approach", ""]
    does = st.get("does")
    if does and one_line("\n".join(does)):
        out += [does[0].strip()] + dedent(does[1:])
    elif not st.fields and trim_blank(st.body):
        out += dedent(trim_blank(st.body))
    out += ["", "## Decisions", "", CONCERN_DECISIONS_HEADER, TABLE_SEP, "",
            "## Questions", "", QUESTIONS_HEADER, TABLE_SEP, "", "## Evidence", ""]
    out += st.evidence
    if st.evidence_paragraph:
        if st.evidence:
            out.append("")
        para = st.evidence_paragraph
        if len(para) == 1:
            out.append("Proof recorded in generation 1, verbatim, not counted by status: %s" % para[0].strip())
        else:
            out += ["Proof recorded in generation 1, verbatim, not counted by status:", ""] + para
    out += ["", "## Shipped"]
    return normalise_blank_lines(out)


def mark_history(p: Proposal, ctx: Context) -> str:
    with open(p.path, "rb") as fh:
        raw = fh.read().decode("utf-8")
    crlf = "\r\n" in raw
    lines = raw.split("\n")
    i = p.status_index
    j = i + 1
    while j < len(lines):
        s = lines[j].rstrip("\r")
        if not s.strip() or s.lstrip().startswith("**") or s.startswith("#"):
            break
        j += 1
    link = rel_link("%s/%s" % (LOOPS_REL, p.slug), os.path.dirname(p.rel), ctx.root) + "/"
    marker = ("**Migrated:** to [`%s/%s/`](%s) on %s. This document is history; the loop skills no longer "
              "track it." % (LOOPS_REL, p.slug, link, ctx.today))
    lines.insert(j, marker + ("\r" if crlf else ""))
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------------
# Report


def step_detail(st: Step) -> str:
    parts = []
    ev = "evidence " + plural(len(st.evidence), "line")
    notes = []
    if st.evidence_no_sha:
        notes.append("%d without a commit" % st.evidence_no_sha)
    if st.evidence_inherited:
        notes.append("%d with the commit of the verdict before" % st.evidence_inherited)
    if st.evidence_foreign_sha:
        notes.append("%d citing a commit not in this repository" % st.evidence_foreign_sha)
    if st.evidence_paragraph:
        notes.append("unparsed text kept verbatim")
    if notes:
        ev += " (%s)" % ", ".join(notes)
    parts.append(ev)
    parts.append("prs " + (", ".join("#" + r if r.isdigit() else r for r in st.prs) if st.prs else "none"))
    if st.touches:
        parts.append("touches %s" % ", ".join(st.touches))
    else:
        parts.append("touches unknown")
    needs = ", ".join(st.needs) if st.needs else "none"
    if st.needs_dropped:
        needs += "; dropped %s" % "; ".join(st.needs_dropped)
    parts.append("needs " + needs)
    return " \u00b7 ".join(parts)


def report(props: List[Proposal], others: List[str], ctx: Context, loop: Optional[LoopMd],
           apply: bool, unknown_only: List[str]) -> List[str]:
    out = []
    mode = "APPLY: writing the plan below" if apply else "DRY RUN: nothing is written; run again with --apply to write this plan"
    out.append("%s, %s" % (TOOL, mode))
    out.append("Repository %s" % ctx.root)
    out.append("Proposals in %s/, loops go to %s/, top environment \"%s\"%s, dated %s"
               % (ctx.proposals_rel, LOOPS_REL, ctx.top,
                  "" if loop else " (no LOOP.md, so the default)", ctx.today))
    main = ctx.git.main_ref()
    out.append("Touches are read from %s" % ("PR merges on `%s`" % main if main else "nowhere: no main branch found"))
    for slug in unknown_only:
        out.append("WARNING: --only %s matches no generation 1 proposal" % slug)
    out.append("")

    counts = {"migrate": 0, "history": 0, "already": 0, "not-selected": 0}
    for p in props:
        counts[p.action] = counts.get(p.action, 0) + 1
    out.append("Proposals: %d with a generation 1 Status line (%d to migrate, %d kept as history, %d already "
               "migrated%s); %s ignored"
               % (len(props), counts["migrate"], counts["history"], counts["already"],
                  (", %d not selected" % counts["not-selected"]) if counts["not-selected"] else "",
                  plural(len(others), "other markdown file")))
    width = max([len(p.slug) for p in props] + [4])
    for p in props:
        tag = {"migrate": "MIGRATE", "history": "HISTORY", "already": "SKIP", "not-selected": "SKIP"}[p.action]
        out.append("  %-7s  %-*s  %s, %s: %s" % (tag, width, p.slug, p.state, p.status_date, p.why))
    if others:
        out.append("  Ignored, no generation 1 Status line: %s" % ", ".join(others))
    out.append("")

    for p in props:
        if p.action != "migrate":
            continue
        loop_rel = "%s/%s/" % (LOOPS_REL, p.slug)
        out.append("=" * 100)
        out.append("%s -> %s   (%s, %s)" % (p.rel, loop_rel, p.state, p.status_date))
        out.append("  \"%s\"" % p.title)
        st = p.readme_stats
        out.append("  README.md: %s, %s, %s%s; %s listed under Shipped"
                   % (plural(st.get("goals", 0), "goal"), plural(st.get("decisions", 0), "decision"),
                      plural(st.get("questions", 0), "question"),
                      ", the defaults" if st.get("defaults") else "",
                      plural(st.get("shipped", 0), "done step")))
        leaves = p.leaf_steps
        n_concern = sum(1 for s in leaves if s.migrate)
        if p.plan_name is not None:
            containers = [s for s in p.steps if s.container]
            out.append("  Plan \"%s\": %s%s; %s, %s as history"
                       % (p.plan_name, plural(len(leaves), "step"),
                          (" (%s)" % "; ".join("%s is a container for %s" % (c.label, ", ".join(k.id for k in c.children))
                                               for c in containers)) if containers else "",
                          ("1 becomes a concern" if n_concern == 1 else "%d become concerns" % n_concern),
                          ("1 stays" if len(leaves) - n_concern == 1 else "%d stay" % (len(leaves) - n_concern))))
        lw = max([len(s.label) for s in p.steps] + [6])
        for s in p.steps:
            if s.container:
                out.append("    %-*s  container  %s" % (lw, s.label, s.reason))
                continue
            if s.migrate:
                tag = "concern %s.md" % s.slug + ("  (done, --include-done)" if s.done else "")
            else:
                tag = "history"
            out.append("    %-*s  %s" % (lw, s.label, tag))
            out.append("    %-*s    why: %s" % (lw, "", s.reason))
            if s.migrate:
                out.append("    %-*s    %s" % (lw, "", step_detail(s)))
        if p.warnings:
            out.append("  Warnings (%d)" % len(p.warnings))
            for w in p.warnings:
                out.append("    [%s] %s" % (w.kind, w.text))
        files = sorted(p.files)
        out.append("  Writes %s in %s%s" % (plural(len(files), "file"), loop_rel,
                   {"add": ", and marks the history file",
                    "present": "; the history file is already marked",
                    "off": "; the history file is left unmarked (--no-mark)"}.get(p.mark_state, "")))
        out.append("")

    out.append("=" * 100)
    out.append("LOOP.md: what /loop-init must still change (this script never edits it)")
    items = loop_md_checklist(loop)
    if items:
        for item in items:
            out.append("  [ ] " + item)
    else:
        out.append("  Nothing: it already reads as generation 2.")
    out.append("")
    out.append("Old skills")
    found = old_skills(ctx.root)
    if found:
        for path in found:
            out.append("  %s" % path)
        out.append("  These are generation 1 copies of skills retired in architect-loop 0.2. Replace them by "
                   "reinstalling architect-loop; this script leaves them alone.")
    else:
        out.append("  None: no generation 1 copy of loop-frame, loop-decide, loop-promote, loop-record or "
                   "loop-reconcile in ~/.claude/skills or .claude/skills.")
    out.append("")

    migrating = [p for p in props if p.action == "migrate"]
    leaves = [s for p in migrating for s in p.leaf_steps]
    concerns = sum(1 for s in leaves if s.migrate)
    ev = sum(len(s.evidence) for s in leaves if s.migrate)
    nosha = sum(s.evidence_no_sha for s in leaves if s.migrate)
    kinds: Dict[str, int] = {}
    for p in migrating:
        for w in p.warnings:
            kinds[w.kind] = kinds.get(w.kind, 0) + 1
    warn_text = ", ".join("%s %d" % (k, v) for k, v in sorted(kinds.items())) or "none"
    backlog = sum(1 for p in migrating if p.state.lower() == "proposed")
    out.append("Summary: %s to migrate (%s), %d kept as history, %d already migrated; %s: %d become concerns, "
               "%d stay as history; %s (%d without a commit); warnings: %s."
               % (plural(counts["migrate"], "proposal"), plural(backlog, "backlog loop"),
                  counts["history"], counts["already"], plural(len(leaves), "step"),
                  concerns, len(leaves) - concerns, plural(ev, "evidence line"), nosha, warn_text))
    return out


# ---------------------------------------------------------------------------------------------
# Main


def fail(message: str) -> int:
    sys.stderr.write("%s: %s\n" % (TOOL, message))
    return 2


def parse_args(argv: Optional[List[str]]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog=TOOL, description="Migrate generation 1 Architect Loop proposals to "
                                                        "generation 2 loops. A dry run unless --apply.")
    ap.add_argument("--repo", default=".", help="the repository (default: the current directory)")
    ap.add_argument("--apply", action="store_true", help="write the plan (default: dry run)")
    ap.add_argument("--only", action="append", default=[], metavar="SLUG",
                    help="migrate only this proposal (repeatable); also migrates a history-state one")
    ap.add_argument("--include-done", action="store_true", help="also turn done steps into concerns")
    ap.add_argument("--no-mark", action="store_true", help="do not add the **Migrated:** line to history files")
    ap.add_argument("--today", metavar="YYYY-MM-DD", help="the date written into the files (default: today)")
    return ap.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if args.today:
        try:
            today = datetime.date.fromisoformat(args.today).isoformat()
        except ValueError:
            return fail("--today must be a date, YYYY-MM-DD: %r" % args.today)
    else:
        today = datetime.date.today().isoformat()

    repo = os.path.abspath(args.repo)
    if not os.path.isdir(repo):
        return fail("%s is not a directory" % repo)
    top_level = Git(repo).run(["rev-parse", "--show-toplevel"])
    if not top_level:
        return fail("%s is not a git repository" % repo)
    root = os.path.normpath(top_level.strip())
    git = Git(root)

    loop_path = os.path.join(root, "LOOP.md")
    loop = LoopMd(loop_path, read_lines(loop_path)) if os.path.isfile(loop_path) else None
    proposals_rel = (loop.proposals_folder() if loop else None) or DEFAULT_PROPOSALS_REL
    proposals_dir = os.path.join(root, proposals_rel)
    if not os.path.isdir(proposals_dir):
        return fail("%s has no generation 1 proposals folder (%s/ does not exist)" % (root, proposals_rel))

    envs, _header, _sec = loop.environments() if loop else ([], None, None)
    top = envs[-1] if envs else "production"
    known_envs = list(dict.fromkeys(envs + [top, "main"])) if envs else list(DEFAULT_ENVS)
    ctx = Context(root, proposals_rel, today, top, known_envs, args.include_done, not args.no_mark, git)

    props: List[Proposal] = []
    others: List[str] = []
    for name in sorted(os.listdir(proposals_dir)):
        path = os.path.join(proposals_dir, name)
        if not name.endswith(".md") or not os.path.isfile(path):
            continue
        rel = "%s/%s" % (proposals_rel, name)
        p = read_proposal(path, rel)
        if p is None:
            others.append(name)
        else:
            props.append(p)

    only = list(dict.fromkeys(args.only))
    slugs = {p.slug for p in props}
    unknown_only = [s for s in only if s not in slugs]
    for p in props:
        state = p.state.lower()
        loop_dir = os.path.join(root, LOOPS_REL, p.slug)
        if only and p.slug not in only:
            p.action, p.why = "not-selected", "not named by --only"
        elif os.path.exists(loop_dir):
            p.action, p.why = "already", "already migrated (%s/%s/ exists)" % (LOOPS_REL, p.slug)
        elif state in MIGRATE_STATES:
            p.action = "migrate"
            p.why = ("becomes a backlog loop" if state == "proposed" else "becomes a loop") + \
                    " in %s/%s/" % (LOOPS_REL, p.slug)
        elif only:
            p.action = "migrate"
            p.why = "becomes a loop in %s/%s/, because --only names it (its state alone would keep it as history)" \
                    % (LOOPS_REL, p.slug)
        elif state in HISTORY_STATES:
            p.action, p.why = "history", "stays in %s/ as history" % proposals_rel
        else:
            p.action, p.why = "history", "unknown state \"%s\": left in %s/; name it with --only to migrate it" \
                % (p.state, proposals_rel)
        if p.action == "migrate":
            plan_proposal(p, ctx)

    for line in report(props, others, ctx, loop, args.apply, unknown_only):
        print(line)

    if args.apply:
        written: List[str] = []
        for p in props:
            if p.action != "migrate":
                continue
            for rel, content in sorted(p.files.items()):
                path = os.path.join(root, rel)
                if os.path.exists(path):
                    continue  # never overwrite
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(content)
                written.append(rel)
            if p.mark_state == "add" and p.mark is not None:
                with open(p.path, "wb") as fh:
                    fh.write(p.mark.encode("utf-8"))
                written.append("%s (marked as history)" % p.rel)
        print("")
        print("Files written (%d):" % len(written))
        for rel in written:
            print("  " + rel)
        if not written:
            print("  none: nothing to migrate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
