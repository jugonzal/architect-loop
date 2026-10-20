#!/usr/bin/env python3
"""Read the questions in a loop's files: each one's number, text, what it blocks, its default, its options and
its recommendation.

Usage:
    python3 questions.py [PATH ...]

PATH is one loop file, a loop's folder (its README.md and one file per concern), or a folder of loops such as
docs/loops/, which is the default. It prints {"questions": [...], "problems": [...]} as JSON.

The format
----------
A loop's README and each concern file have a `## Questions` section. Its table has four columns, and a question
that has been answered is struck through, with a pointer to what answered it:

    | # | Question | Blocks | Default if unanswered |
    | --- | --- | --- | --- |
    | Q1 | Where do exports run? | C2 | In the web process, behind a 30-second timeout |
    | ~~Q2~~ | ~~CSV or JSON?~~ → D1 | | |

Under the table, each question with options has a list headed by its number. Each option is its text in bold, a
colon and its main consequence; it may wrap onto lines indented by two spaces. The recommended option ends with
`(recommended)`. A question takes 2 to 4 options, and an answered question keeps its list:

    **Q1 options**
    - **In the web process**: nothing new to deploy, but a large export times out.
    - **In a queue worker**: no timeout, but it waits for the worker concern. (recommended)

    **Q2 options**
    - **CSV**: opens in any spreadsheet; nested fields are flattened. (recommended)
    - **JSON**: keeps nested fields, but needs a converter to read.

The default is what happens if nobody answers, so it is kept apart from the recommendation. A question written
before this format, with no list, reads with no options and no recommendation, whatever its text says. HTML
comments and fenced code are never read, so a template's example in a kept guidance comment is not a question.

What it returns
---------------
Each question is a JSON object:

    ref             <loop>/Q1 for a README, <loop>/<concern>/Q1 for a concern
    file, line      where its table row is
    number          Q1
    question        its text, without the strike-through
    open            false once its number or its text is struck through
    answer          what follows the struck text, such as "D1"; null while open
    blocks          the Blocks cell, split at its top-level commas
    default         the "Default if unanswered" cell, or null
    options         [{"text": ..., "consequence": ...}], [] when it has no list
    recommendation  the text of the option marked (recommended), or null

Each problem is {"file", "line", "message"}: a list the format cannot read as written, a recommendation marked
twice or not at all on an open question, a row without a number or a question. A problem never stops the read:
everything else is returned, so a board can show what it can and name what it could not read.

Exit status: 0 when nothing is wrong, 1 when there is a problem (the JSON is still printed, and each problem is
listed on stderr), 2 when a PATH does not exist.

Standard library only; Python 3.8 or later. loop-plan and loop-design write this format, and every other reader
of questions imports this module rather than parsing them itself.
"""

import argparse
import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
QUESTIONS_RE = re.compile(r"^(?:\d+\.\s*)?(?:open\s+)?questions$", re.I)
FENCE_RE = re.compile(r"^\s*(```|~~~)")
SEPARATOR_CELL_RE = re.compile(r"^:?-{3,}:?$")
NUMBER_RE = re.compile(r"^Q\d+$")
OPTIONS_RE = re.compile(r"^\*\*(Q\d+) options:?\*\*:?$")
NEAR_OPTIONS_RE = re.compile(r"^[\s*_~#>-]*Q\d+[\s*_~]+options\b", re.I)
OPTION_RE = re.compile(r"^- \*\*(.+?)\*\*:[ \t]*(.*)$")
RECOMMENDED_RE = re.compile(r"\s*\(recommended\)\s*$", re.I)
MARKER_RE = re.compile(r"\(recommended\)", re.I)
EMPTY_CELLS = {"", "-", "–", "—"}
OPTION_FORM = "- **<option>**: <consequence>"
MIN_OPTIONS, MAX_OPTIONS = 2, 4


def strip_comments(text: str) -> str:
    """Remove HTML comments, keeping every line where it was."""
    out, pos = [], 0
    while True:
        start = text.find("<!--", pos)
        if start < 0:
            out.append(text[pos:])
            return "".join(out)
        end = text.find("-->", start + 4)
        stop = len(text) if end < 0 else end + 3
        out.append(text[pos:start])
        out.append("\n" * text.count("\n", start, stop))
        pos = stop


def question_sections(lines: List[str]) -> List[Tuple[int, int]]:
    """(first, end) line indexes of the body of each `## Questions` section."""
    sections, start, fence = [], None, False
    for i, line in enumerate(lines):
        if FENCE_RE.match(line):
            fence = not fence
            continue
        m = None if fence else HEADING_RE.match(line)
        if m and len(m.group(1)) <= 2:
            if start is not None:
                sections.append((start, i))
                start = None
            if len(m.group(1)) == 2 and QUESTIONS_RE.match(m.group(2)):
                start = i + 1
    if start is not None:
        sections.append((start, len(lines)))
    return sections


def split_row(line: str) -> List[str]:
    """A table row's cells, with `\\|` read as a pipe inside a cell."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells, cell, i = [], [], 0
    while i < len(s):
        if s[i] == "\\" and s[i + 1:i + 2] == "|":
            cell.append("|")
            i += 2
            continue
        if s[i] == "|":
            cells.append("".join(cell).strip())
            cell = []
        else:
            cell.append(s[i])
        i += 1
    cells.append("".join(cell).strip())
    return cells


def is_separator(line: str) -> bool:
    return line.strip().startswith("|") and all(SEPARATOR_CELL_RE.match(c) for c in split_row(line))


def unstrike(cell: str) -> Tuple[str, bool, str]:
    """(text, struck, what follows it) for a cell that may start with ~~text~~."""
    if cell.startswith("~~"):
        end = cell.find("~~", 2)
        if end > 2:
            rest = cell[end + 2:].strip()
            if rest.startswith("→") or rest.startswith("->"):
                rest = rest[1 if rest.startswith("→") else 2:].strip()
            return cell[2:end].strip(), True, rest
    return cell, False, ""


def split_blocks(cell: str) -> List[str]:
    """The Blocks cell as a list, split at commas outside parentheses, brackets and code."""
    if cell in EMPTY_CELLS:
        return []
    parts, part, depth, code = [], [], 0, False
    for c in cell:
        if c == "`":
            code = not code
        elif not code and c in "([":
            depth += 1
        elif not code and c in ")]":
            depth = max(0, depth - 1)
        if c == "," and depth == 0 and not code:
            parts.append("".join(part).strip())
            part = []
            continue
        part.append(c)
    parts.append("".join(part).strip())
    return [p for p in parts if p]


class Reader:
    def __init__(self, source: str, ref_prefix: Optional[str]):
        self.source = source
        self.prefix = ref_prefix
        self.rows = []  # type: List[dict]
        self.lists = []  # type: List[Tuple[str, int, List[Tuple[int, str]]]]
        self.problems = []  # type: List[dict]

    def problem(self, index: int, message: str) -> None:
        self.problems.append({"file": self.source, "line": index + 1, "message": message})

    def read(self, text: str) -> Dict[str, list]:
        lines = strip_comments(text).splitlines()
        for first, end in question_sections(lines):
            self.read_section(lines, first, end)
        self.attach()
        self.problems.sort(key=lambda p: p["line"])
        return {"questions": self.rows, "problems": self.problems}

    def read_section(self, lines: List[str], i: int, end: int) -> None:
        fence = False
        while i < end:
            line = lines[i]
            if FENCE_RE.match(line):
                fence = not fence
                i += 1
                continue
            stripped = line.strip()
            if fence or not stripped:
                i += 1
            elif stripped.startswith("|") and i + 1 < end and is_separator(lines[i + 1]):
                i = self.read_table(lines, i, end)
            elif OPTIONS_RE.match(stripped):
                i = self.read_list(lines, i, end, OPTIONS_RE.match(stripped).group(1))
            else:
                if NEAR_OPTIONS_RE.match(stripped):
                    self.problem(i, "a list of options is headed **Q<n> options**, in bold, alone on its line")
                i += 1

    def read_table(self, lines: List[str], i: int, end: int) -> int:
        header = [c.lower() for c in split_row(lines[i])]
        columns = {name: header.index(name) for name in ("#", "question", "blocks", "default if unanswered")
                   if name in header}
        if "#" not in columns or "question" not in columns:
            self.problem(i, "a table under Questions needs a # and a Question column")
            columns = {}
        i += 2
        while i < end and lines[i].strip().startswith("|"):
            if columns:
                self.read_row(i, split_row(lines[i]), columns)
            i += 1
        return i

    def read_row(self, i: int, cells: List[str], columns: Dict[str, int]) -> None:
        def cell(name: str) -> str:
            at = columns.get(name)
            return cells[at] if at is not None and at < len(cells) else ""

        if not any(cells):
            return
        number, number_struck, _ = unstrike(cell("#"))
        if not NUMBER_RE.match(number):
            self.problem(i, "the first cell, \"%s\", is not Q and a number" % cell("#"))
            return
        question, text_struck, answer = unstrike(cell("question"))
        if not question:
            self.problem(i, "%s has no question" % number)
            return
        if any(row["number"] == number for row in self.rows):
            self.problem(i, "%s is in the table twice; numbers are never reused" % number)
            return
        answered = number_struck or text_struck
        default = cell("default if unanswered")
        self.rows.append({
            "ref": "%s/%s" % (self.prefix, number) if self.prefix else number,
            "file": self.source,
            "line": i + 1,
            "number": number,
            "question": question,
            "open": not answered,
            "answer": (answer or None) if answered else None,
            "blocks": split_blocks(cell("blocks")),
            "default": None if default in EMPTY_CELLS else default,
            "options": [],
            "recommendation": None,
        })

    def read_list(self, lines: List[str], i: int, end: int, number: str) -> int:
        head, items = i, []
        i += 1
        while i < end:
            line = lines[i]
            if not line.strip():
                i += 1
            elif line.startswith("- ") or line.strip() == "-":
                items.append((i, line.strip()))
                i += 1
            elif items and line.startswith("  "):
                items[-1] = (items[-1][0], items[-1][1] + " " + line.strip())
                i += 1
            else:
                break
        self.lists.append((number, head, items))
        return i

    def attach(self) -> None:
        rows = {row["number"]: row for row in self.rows}
        seen = set()
        for number, head, items in self.lists:
            if number not in rows:
                self.problem(head, "options for %s, but %s is not in the table" % (number, number))
                continue
            if number in seen:
                self.problem(head, "a second list of options for %s; only the first is read" % number)
                continue
            seen.add(number)
            row = rows[number]
            options, recommended = self.read_options(number, items)
            row["options"] = options
            if not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
                self.problem(head, "%s has %d option%s; a question takes %d to %d"
                             % (number, len(options), "" if len(options) == 1 else "s", MIN_OPTIONS, MAX_OPTIONS))
            if len(recommended) == 1:
                row["recommendation"] = recommended[0]
            elif recommended:
                self.problem(head, "%s marks %d options (recommended); mark one" % (number, len(recommended)))
            elif row["open"] and options:
                self.problem(head, "%s is open and has options, but none is marked (recommended)" % number)

    def read_options(self, number: str, items: List[Tuple[int, str]]) -> Tuple[List[dict], List[str]]:
        options, recommended, texts = [], [], set()
        for i, item in items:
            m = OPTION_RE.match(item)
            if not m:
                self.problem(i, "an option is written %s" % OPTION_FORM)
                continue
            text, consequence = m.group(1).strip(), m.group(2).strip()
            marked = bool(RECOMMENDED_RE.search(consequence))
            consequence = RECOMMENDED_RE.sub("", consequence).strip()
            if not consequence:
                self.problem(i, "the option \"%s\" has no consequence; write %s" % (text, OPTION_FORM))
                continue
            if MARKER_RE.search(text) or MARKER_RE.search(consequence):
                self.problem(i, "(recommended) goes at the end of the option's line, after its consequence")
            if text in texts:
                self.problem(i, "%s has two options that read \"%s\"" % (number, text))
                continue
            texts.add(text)
            options.append({"text": text, "consequence": consequence})
            if marked:
                recommended.append(text)
        return options, recommended


def parse(text: str, source: str = "<text>", ref_prefix: Optional[str] = None) -> Dict[str, list]:
    """Read the questions in one file's text. ref_prefix is <loop> or <loop>/<concern>."""
    return Reader(source, ref_prefix).read(text)


def ref_prefix(path: str) -> str:
    """<loop> for a loop's README.md, <loop>/<concern> for a concern's file."""
    loop = os.path.basename(os.path.dirname(os.path.abspath(path)))
    stem = os.path.splitext(os.path.basename(path))[0]
    return loop if stem == "README" else "%s/%s" % (loop, stem)


def read_file(path: str) -> Dict[str, list]:
    with open(path, encoding="utf-8") as f:
        return parse(f.read(), source=path, ref_prefix=ref_prefix(path))


def merge(results: List[Dict[str, list]]) -> Dict[str, list]:
    return {"questions": [q for r in results for q in r["questions"]],
            "problems": [p for r in results for p in r["problems"]]}


def read_loop(folder: str) -> Dict[str, list]:
    """A loop's README.md first, then each concern's file in name order."""
    names = sorted(n for n in os.listdir(folder) if n.endswith(".md") and n != "README.md")
    if os.path.isfile(os.path.join(folder, "README.md")):
        names.insert(0, "README.md")
    return merge([read_file(os.path.join(folder, n)) for n in names])


def read_loops(root: str) -> Dict[str, list]:
    """Every loop in a folder of loops, such as docs/loops/, in name order."""
    folders = sorted(n for n in os.listdir(root) if os.path.isdir(os.path.join(root, n)))
    return merge([read_loop(os.path.join(root, n)) for n in folders])


def read_path(path: str) -> Dict[str, list]:
    if os.path.isfile(path):
        return read_file(path)
    if os.path.isfile(os.path.join(path, "README.md")):
        return read_loop(path)
    return read_loops(path)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Read the questions in a loop's files as JSON.")
    parser.add_argument("paths", nargs="*", default=[os.path.join("docs", "loops")], metavar="PATH",
                        help="a loop file, a loop's folder, or a folder of loops (default: docs/loops)")
    args = parser.parse_args(argv)
    missing = [p for p in args.paths if not os.path.exists(p)]
    if missing:
        for p in missing:
            print("questions.py: no such file or folder: %s" % p, file=sys.stderr)
        return 2
    result = merge([read_path(p) for p in args.paths])
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    for p in result["problems"]:
        print("%s:%d: %s" % (p["file"], p["line"], p["message"]), file=sys.stderr)
    return 1 if result["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
