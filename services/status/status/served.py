"""What each environment serves, read only with an HTTP GET (command-center/D9, D56).

For each row of LOOP.md §3, the service GETs the first `http(s)` URL in the row's served-commit cell, which answers
`{"commit": "<sha>"}` by the deploy convention (command-center/D32). It never runs the cell's command, or anything
else taken from the repository. A row without a URL is unknown, as is a row that agents may not read, which the
terminal does not read either. The `main` row is the main branch itself: its served commit is main's head, which
the service has just fetched with git, as the terminal's command for it prints.

A read that fails, times out, or answers anything but a commit is unknown, with the reason. Nothing read before is
ever kept to stand in for it.
"""

import json
import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

USER_AGENT = "architect-loop-status"
URL_RE = re.compile(r"https?://[^\s`'\"<>|()\[\]{}\\]+")
COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")
MAX_BODY = 65536


def _cells(ls, loop_md):
    """{row name: its served-commit cell}, read with the derivation's own table reader."""
    if not loop_md:
        return {}
    _, sections = ls.outline(loop_md)
    body = next((lines for name, lines in sections.items() if name.endswith("environments")), None)
    if body is None:
        return {}
    for i in range(len(body) - 1):
        if body[i].strip().startswith("|") and ls.questions.is_separator(body[i + 1]):
            header = [c.lower() for c in ls.questions.split_row(body[i])]
            table = body[i + 2:]
            break
    else:
        return {}
    name_at = next((n for n, c in enumerate(header) if c.startswith("environment")), None)
    served_at = next((n for n, c in enumerate(header) if c.startswith("served commit")), None)
    cells = {}
    for line in table:
        if not line.strip().startswith("|"):
            break
        row = ls.questions.split_row(line)
        name = row[name_at] if name_at is not None and name_at < len(row) else ""
        name = name.replace("`", "").replace("*", "").strip()
        if name and name not in cells:
            cells[name] = row[served_at] if served_at is not None and served_at < len(row) else ""
    return cells


def url_in(cell):
    """The first http(s) URL in a served-commit cell, without trailing punctuation, or None (command-center/D56)."""
    match = URL_RE.search(cell or "")
    return match.group(0).rstrip(".,;:") if match else None


def rows(ls, loop_md):
    """LOOP.md §3's rows in the derivation's order, each {name, url, error}: the URL to GET, or why there is none."""
    cells = _cells(ls, loop_md)
    out = []
    for row in ls.environment_rows(loop_md):
        name = row["name"]
        url, error = None, None
        if name == "main":
            pass
        elif not row["readable"]:
            error = row["error"]
        else:
            url = url_in(cells.get(name, ""))
            if url is None:
                error = row["error"] or ("LOOP.md §3's served-commit cell for %s names no http(s) URL to read "
                                         "(command-center/D56)" % name)
        out.append({"name": name, "url": url, "error": error})
    return out


def commit_of(body):
    """The commit a /version answer names, lowercased, or None."""
    try:
        value = json.loads(body)
    except ValueError:
        return None
    commit = value.get("commit") if isinstance(value, dict) else None
    if not isinstance(commit, str) or not COMMIT_RE.match(commit.lower()):
        return None
    return commit.lower()


def read(url, timeout):
    """(commit, None) from a GET of url, or (None, why not)."""
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status, body = response.status, response.read(MAX_BODY)
    except urllib.error.HTTPError as error:
        return None, "GET %s answered %d" % (url, error.code)
    except (urllib.error.URLError, OSError, TimeoutError, ValueError) as error:
        reason = getattr(error, "reason", None) or error
        return None, "GET %s failed: %s" % (url, reason)
    if status != 200:
        return None, "GET %s answered %d" % (url, status)
    try:
        json.loads(body)
    except ValueError:
        return None, "GET %s is not JSON" % url
    commit = commit_of(body)
    if commit is None:
        return None, "GET %s names no commit" % url
    return commit, None


def environments(ls, loop_md, main_sha, timeout):
    """The facts document's environments: [{name, served, error}] in LOOP.md §3's order, main first if it has no
    row, as loop_status.py gather writes them, with every URL read at once."""
    found = rows(ls, loop_md)
    with ThreadPoolExecutor(max_workers=8) as pool:
        reads = {r["name"]: pool.submit(read, r["url"], timeout) for r in found if r["url"]}
        out = []
        if not any(r["name"] == "main" for r in found):
            out.append({"name": "main", "served": main_sha, "error": None})
        for r in found:
            if r["name"] == "main":
                out.append({"name": "main", "served": main_sha, "error": None})
            elif r["url"]:
                served, error = reads[r["name"]].result()
                out.append({"name": r["name"], "served": served, "error": error})
            else:
                out.append({"name": r["name"], "served": None, "error": r["error"]})
    return out
