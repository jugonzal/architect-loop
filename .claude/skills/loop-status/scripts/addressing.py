#!/usr/bin/env python3
"""Address each item of the loop-status queue: the gate it crosses, the one person it waits on, and who else sees it.

loop_status.py builds the queue (step 6 of loop-status's SKILL.md), then hands each item to a Book, so the terminal
board and the status document address items the same way. This module reads only the texts it is given (LOOP.md
and the loop READMEs' front matter, as they are on main); it runs nothing.

The rules, which step 6 of the SKILL.md states and this module implements:

- A person is their GitHub login, in waits_on and visible_to, in a loop README's `owner:` and `members:`, and as
  each gate's holder in LOOP.md §2.
- Each gate line in LOOP.md §2 names its key and its one holder: `- **Secrets** (key: secrets; holder: ana): ...`.
  A holder that is not a login (empty, or a placeholder such as <login>) is no holder.
- An effect, and a question whose answer crosses a gate, ends with a parenthesis whose last part names its keys:
  `(the owner rotates it; gates: secrets, infra)`. questions.py's gate_keys reads them, for both.
- A review and a refused loop-document PR cross `merge`. A ship is split by gate (split_ship): one item for each key
  other than `merge` and `deploy` its concerns' effects name, plus one that crosses `deploy`. A question crosses
  the key it names, when it names exactly one. A record, a proof and a contradiction cross none.
- An item waits on its gate's holder; with no gate, or no holder, on its loop's owner: the README's `owner:`, or
  else the login LOOP.md §1 gives in parentheses after the owner's name, as in "Ana (ana on GitHub)". An item that
  spans loops whose owners differ waits on §1's. With no one named, it waits on None, and drift says why.
- visible_to is the `members:` of the item's loop (of each of its loops, for an item that spans loops).
- Keys match exactly. A key §2 does not define is not a gate, and is drift. While §2 names no keys at all, KEYS
  stand in for it: an item still crosses the gate its key names when the key is one of them, it waits on its
  loop's owner, and one drift line says §2 names no keys.

Standard library only; Python 3.8 or later.
"""

import importlib.util
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("loop_status_questions", os.path.join(HERE, "questions.py"))
questions = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(questions)

# The gate keys LOOP.md §2 uses by default (loop-init's template defines each one), in the template's order.
KEYS = ("merge", "deploy", "migration", "release", "store", "money", "spending", "identity", "secrets", "legal",
        "infra", "prod-data", "send")
# The gates every ship and review crosses whatever its effects say: they are not split out of a ship.
MERGE, DEPLOY = "merge", "deploy"

LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
OWNER_RE = re.compile(r"\*\*Owner:?\*\*:?(.*?)(?=\s-\s\*\*|$)")
LOGIN_IN_PARENS_RE = re.compile(r"\(\s*(@?[A-Za-z0-9][A-Za-z0-9-]*)\s*(?:\)|\s+on\s)")
GATE_RE = re.compile(r"\(\s*key:\s*([^;()\s]+)\s*(?:;\s*holder:\s*([^;)]*?)\s*)?\)")


def login(value):
    """A GitHub login as written, or None when the value is not one. An @ before it and code quotes are allowed."""
    if not isinstance(value, str):
        return None
    value = value.strip().strip("`").strip()
    if value.startswith("@"):
        value = value[1:]
    return value if LOGIN_RE.match(value) else None


def section(text, name):
    """The lines of LOOP.md's level-2 section whose name, without its numbering, starts with name; [] if none.
    HTML comments and fenced code are left out."""
    if not text:
        return []
    out, inside, fence = [], False, False
    for line in questions.strip_comments(text).split("\n"):
        if FENCE_RE.match(line):
            fence = not fence
            continue
        m = None if fence else HEADING_RE.match(line)
        if m and len(m.group(1)) <= 2:
            title = re.sub(r"^\d+(\.\d+)*\.?\s*", "", m.group(2)).strip().lower()
            inside = len(m.group(1)) == 2 and title.startswith(name)
            continue
        if inside and not fence:
            out.append(line)
    return out


def owner_login(loop_md):
    """The login LOOP.md §1 gives in parentheses after the owner's name, as in "Juan (jugonzal on GitHub)" or
    "Ana (ana)": read from the Owner bullet only, so no other parenthesis in §1 is taken for a login."""
    bullet = OWNER_RE.search(" ".join(line.strip() for line in section(loop_md, "roles")))
    m = LOGIN_IN_PARENS_RE.search(bullet.group(1)) if bullet else None
    return login(m.group(1)) if m else None


def read_gates(loop_md):
    """Every (key, holder) LOOP.md §2 names, in order; holder is None when the line names no login."""
    out = []
    for line in section(loop_md, "gates"):
        for m in GATE_RE.finditer(line):
            out.append((m.group(1).strip("`"), login(m.group(2)) if m.group(2) else None))
    return out


def gate_holders(loop_md):
    """{key: holder or None} for the gates LOOP.md §2 names; {} when it names no keys. The first line wins."""
    out = {}
    for key, holder in read_gates(loop_md):
        out.setdefault(key, holder)
    return out


class Book:
    """Who waits on what in one project: the gates LOOP.md §2 names and their holders, the owner §1 names, and each
    loop's owner and members. Its drift lists what it could not address as written."""

    def __init__(self, loop_md, loops):
        """loop_md is LOOP.md's text, or None. loops is [{id, path, owner, members, parked}], with owner and members
        as the README's front matter writes them (a string or None, and a list of strings)."""
        self.drift = []
        self.project_owner = owner_login(loop_md)
        gates = read_gates(loop_md)
        self.holders = gate_holders(loop_md)
        self.named = bool(self.holders)
        self.known = set(self.holders) if self.named else set(KEYS)
        twice = sorted({key for key, _ in gates if sum(1 for k, _ in gates if k == key) > 1})
        if twice:
            self.add("LOOP.md, §2", "it defines %s more than once, and a gate has one holder; the first line counts"
                     % ", ".join(twice), "the (key: ...; holder: ...) lines of LOOP.md §2")
        if loop_md is not None and not self.named:
            self.add("LOOP.md, §2", "it names no gate keys, so every item waits on its loop's owner. Give each gate "
                     "its key and holder, as (key: secrets; holder: <login>)", "LOOP.md §2 on main")
        self.loops, nobody = {}, []
        for loop in loops:
            owner = login(loop.get("owner"))
            if loop.get("owner") and owner is None:
                self.add("%s, front matter" % loop["path"], "owner: %s is not a GitHub login, so its items wait on "
                         "%s" % (loop["owner"], "LOOP.md §1's owner" if self.project_owner else "no one"),
                         "the README's front matter")
            members = []
            for raw in loop.get("members") or []:
                person = login(raw)
                if person is None:
                    self.add("%s, front matter" % loop["path"], "members: %s is not a GitHub login, so that member "
                             "sees nothing" % raw, "the README's front matter")
                elif person not in members:
                    members.append(person)
            self.loops[loop["id"]] = {"owner": owner or self.project_owner, "members": members}
            if not (owner or self.project_owner) and not loop.get("parked"):
                nobody.append(loop["id"])
        if nobody:
            self.add("LOOP.md, §1", "%s, and %s %s no owner:, so %s items wait on no one" % (
                "there is no LOOP.md" if loop_md is None else
                "it gives the owner no GitHub login in parentheses after their name",
                ", ".join(nobody), "has" if len(nobody) == 1 else "have", "its" if len(nobody) == 1 else "their"),
                "LOOP.md §1 and each loop README's front matter")

    def add(self, where, finding, checked):
        self.drift.append({"where": where, "finding": finding, "checked": checked})

    # Gates.

    def gates(self, text):
        """(gates, unknown): the keys a text names that are gates here, and the ones that are not."""
        keys = questions.gate_keys(text)
        return [k for k in keys if k in self.known], [k for k in keys if k not in self.known]

    def split_ship(self, concerns):
        """A ship split by gate: [(gate, concern refs, manual steps)], deploy first. concerns is [(ref, effects)].
        Each key other than merge and deploy gets the effects that name it; deploy gets every concern, and the
        effects that name deploy or no other gate."""
        deploy, gated = [], {}
        for ref, effects in concerns:
            for effect in effects:
                gates, _ = self.gates(effect)
                others = [g for g in gates if g not in (MERGE, DEPLOY)]
                for gate in others:
                    refs, steps = gated.setdefault(gate, ([], []))
                    if ref not in refs:
                        refs.append(ref)
                    if effect not in steps:
                        steps.append(effect)
                if (not others or DEPLOY in gates) and effect not in deploy:
                    deploy.append(effect)
        return [(DEPLOY, [ref for ref, _ in concerns], deploy)] + [(g, r, s) for g, (r, s) in gated.items()]

    def question_gate(self, text):
        gates, unknown = self.gates(text)
        return gates[0] if len(gates) == 1 and not unknown else None

    # People.

    def owner(self, loop_ids):
        """The owner of these loops when they share one, else LOOP.md §1's; None when no one is named."""
        owners = {self.loops[i]["owner"] for i in loop_ids if i in self.loops}
        return owners.pop() if len(owners) == 1 else self.project_owner

    def address(self, item):
        """Fill an item's gate (a ship's is already set, by split_ship), waits_on and visible_to."""
        kind = item["kind"]
        if kind in ("review", "refused_pr"):
            item["gate"] = MERGE
        elif kind == "question":
            item["gate"] = self.question_gate(item["detail"]["question"])
        elif kind != "ship":
            item["gate"] = None
        loop_ids = [item["loop"]] if item["loop"] else list(dict.fromkeys(c.split("/")[0] for c in item["concerns"]))
        holder = self.holders.get(item["gate"]) if item["gate"] else None
        item["waits_on"] = holder or self.owner(loop_ids)
        visible = []
        for loop_id in loop_ids:
            for person in self.loops.get(loop_id, {}).get("members", []):
                if person not in visible:
                    visible.append(person)
        item["visible_to"] = visible
        return item

    # Drift.

    def check(self, effects, questions_):
        """Drift for the keys the effects and open questions name that §2 does not define (only once §2 names
        keys), and for a question that names more than one. effects is [(concern path, effect)]; questions_ is the
        open questions as questions.py reads them."""
        out = []
        for path, effect in effects:
            _, unknown = self.gates(effect)
            if unknown and self.named:
                out.append({"where": "%s, effects" % path,
                            "finding": "the effect \"%s\" names %s, which LOOP.md §2 does not define, so no item "
                                       "crosses %s" % (effect, ", ".join(unknown), "it" if len(unknown) == 1 else
                                                       "them"),
                            "checked": "the gate keys of LOOP.md §2"})
        for q in questions_:
            keys = questions.gate_keys(q["question"])
            _, unknown = self.gates(q["question"])
            where = "%s:%d, Questions" % (q["file"], q["line"])
            if len(keys) > 1:
                out.append({"where": where, "finding": "%s names %s, but a question crosses at most one gate, so it "
                            "crosses none" % (q["number"], ", ".join(keys)), "checked": "its Question cell"})
            elif unknown and self.named:
                out.append({"where": where, "finding": "%s names %s, which LOOP.md §2 does not define, so it crosses "
                            "no gate" % (q["number"], unknown[0]), "checked": "the gate keys of LOOP.md §2"})
        return out
