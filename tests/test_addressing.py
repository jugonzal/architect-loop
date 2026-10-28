"""Tests for plugin/skills/loop-status/scripts/addressing.py: who each queue item waits on, and the gate it crosses.

command-center/addressed-to-people:
- C1: each queue item names exactly one person in waits_on: the holder LOOP.md §2 names for the gate it crosses,
  and otherwise the loop's owner. A loop with no owner: falls back to the login LOOP.md §1 gives in parentheses, and
  a gate §2 names no holder for waits on the loop's owner. A person is their GitHub login (command-center/D62,
  D65). ReadingTest reads logins, §1's owner and §2's keys and holders; WaitsOnTest derives small worlds with and
  without an owner and with gated and ungated effects.
- C2: each item lists the loop's members: in visible_to, and the terminal board shows who each item waits on
  (command-center/D10). VisibleToTest.
- C3: each item's gate comes from the keys of command-center/D58 (per D38). A review crosses merge; a ship is split
  into one item per key its concerns' effects carry other than merge, plus one for deploy (D59); a refused
  loop-document PR crosses merge, and record, proof and contradiction items cross none (D63); a question crosses
  the key its Question cell ends with (D60, D64). Once §2 names keys, a key it does not define is drift; while it
  names none, one drift line says so and items still show their gate (D65). GateTest and NoKeysTest; the fixture
  world of tests/test_loop_status.py shows the same through gathered and supplied facts.

command-center/status-people:
- C1: each loop in the document carries owner, its front matter's login, else the one LOOP.md §1 gives, and null
  when neither is known, and members, the logins in its front matter (command-center/D70, D62). LoopPeopleTest; the
  fixture world of tests/test_loop_status.py shows the same through gathered and supplied facts and the command line.

Every document derived here validates against status.schema.json (check_document, from test_loop_status.py).

Run from the repository root: python3 -m unittest discover -s tests -v
"""

import importlib.util
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from test_loop_status import Mini, check_document, concern_md, ls  # noqa: E402

ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(ROOT, "plugin", "skills", "loop-status", "scripts")
SKILL = os.path.join(ROOT, "plugin", "skills", "loop-status", "SKILL.md")
LOOP_INIT_TEMPLATE = os.path.join(ROOT, "plugin", "skills", "loop-init", "templates", "LOOP.md")
LOOP_PLAN_TEMPLATES = os.path.join(ROOT, "plugin", "skills", "loop-plan", "templates")
FIXTURES = os.path.join(HERE, "fixtures", "addressing")


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


addressing = module("addressing", "addressing.py")
questions = module("questions", "questions.py")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


KEYED = read(os.path.join(FIXTURES, "LOOP.md"))
NO_KEYS = read(os.path.join(FIXTURES, "no-keys", "LOOP.md"))
PROOF = "## How it was proven before the merge\n\n- [x] C1: HOLDS (rung 5, local)\n\nConcern: loop/thing\n"
THIRTEEN = ("merge", "deploy", "migration", "release", "store", "money", "spending", "identity", "secrets", "legal",
            "infra", "prod-data", "send")


def items(doc):
    return {i["id"]: i for i in doc["queue"]}


def drift(doc, where):
    return [d for d in doc["drift"] if d["where"] == where]


def world(loop_md=KEYED, front=None):
    """A Mini whose LOOP.md is loop_md, with loop/README.md's front matter set to front."""
    m = Mini()
    m.files["LOOP.md"] = loop_md
    if front is not None:
        m.loop("loop", front=front)
    return m


def merged(m, effects, ref="loop/thing", number=1):
    """ref merged into main, and staging not serving it: one ship to staging."""
    m.land(ref, number)
    m.concern(ref, concern_md(effects=effects))


class ReadingTest(unittest.TestCase):
    """C1's inputs: a person is a GitHub login (D62), §1 names the owner's, and §2 each gate's key and holder."""

    def test_a_person_is_a_github_login(self):
        self.assertEqual(addressing.login("jugonzal"), "jugonzal")
        self.assertEqual(addressing.login(" @dan "), "dan")
        self.assertEqual(addressing.login("`ana-b2`"), "ana-b2")
        for value in (None, "", "<login>", "Juan Gonzalez", "-ana", "ana-", "a--b", "TODO(owner)", "x" * 40):
            self.assertIsNone(addressing.login(value), value)

    def test_the_owner_is_the_login_section_1_gives_in_parentheses(self):
        self.assertEqual(addressing.owner_login("## 1. Roles\n\n- **Owner:** Juan (jugonzal on GitHub). Sets goals.\n"),
                         "jugonzal")
        self.assertEqual(addressing.owner_login(read(os.path.join(HERE, "fixtures", "loop_status", "project",
                                                                  "LOOP.md"))), "ana", "Ana (ana on the forge)")
        self.assertEqual(addressing.owner_login(KEYED), "ana")
        for text in (None, "", "## 1. Roles\n\n- **Owner:** Juan. Sets goals.\n",
                     "## 1. Roles\n\n- **Owner:** <name> (<GitHub login> on GitHub).\n",
                     "## 2. Gates\n\n- **Owner:** Juan (jugonzal on GitHub).\n"):
            self.assertIsNone(addressing.owner_login(text), text)

    def test_section_2_names_each_gates_key_and_holder(self):
        self.assertEqual(addressing.gate_holders(KEYED), {
            "merge": "ana", "deploy": "ben", "store": None, "secrets": "carla", "infra": "dan", "money": None,
            "hardware": "erin"})

    def test_a_section_2_written_before_keys_names_none(self):
        self.assertEqual(addressing.gate_holders(NO_KEYS), {})
        self.assertEqual(addressing.gate_holders(None), {})

    def test_an_effect_or_a_question_names_its_gates_in_its_closing_parenthesis(self):
        cases = {
            "an API key rotated in production (the owner rotates it; gates: secrets)": ["secrets"],
            "a DNS record and its certificate (the owner adds them; gates: infra, secrets)": ["infra", "secrets"],
            "Delete exports after 30 days? (gates: prod-data)": ["prod-data"],
            "a release (the owner cuts it per D17 (see §2); gates: release)": ["release"],
            "a step (gates: `money`)": ["money"],
            "the SMTP password in production's secret store (secrets)": [],
            "a migration on shared data": [],
            "a step (gates: money) and then more": [],
            "a step (gates: )": [],
            "": [],
        }
        for text, keys in cases.items():
            self.assertEqual(questions.gate_keys(text), keys, text)

    def test_the_skill_and_the_loop_init_template_name_the_thirteen_keys(self):
        self.assertEqual(addressing.KEYS, THIRTEEN)
        template = read(LOOP_INIT_TEMPLATE)
        self.assertEqual(addressing.gate_holders(template), {k: None for k in THIRTEEN},
                         "the template defines every key, each holder still a placeholder")
        self.assertIsNone(addressing.owner_login(template), "the template's owner is a placeholder")
        self.assertIn("(<GitHub login> on GitHub)", template)
        skill = read(SKILL)
        self.assertIn("[scripts/addressing.py](scripts/addressing.py)", skill)
        for key in THIRTEEN:
            self.assertIn("`%s`" % key, skill, key)

    def test_the_loop_plan_templates_show_owner_members_and_gates(self):
        loop = read(os.path.join(LOOP_PLAN_TEMPLATES, "loop.md"))
        front = ls.front_matter(loop)
        self.assertEqual(sorted(front), ["members", "owner"])
        self.assertIsNone(addressing.login(front["owner"]), "the owner is a placeholder until loop-plan fills it")
        self.assertEqual(ls.fm_list(front, "members"), [])
        concern = read(os.path.join(LOOP_PLAN_TEMPLATES, "concern.md"))
        examples = [s for s in re.findall(r"`([^`]*gates:[^`]*)`", concern) if s.startswith("[")]
        self.assertTrue(examples, "concern.md shows effects ending in (...; gates: <key>)")
        for example in examples:
            for effect in ls.fm_list({"effects": example}, "effects"):
                keys = questions.gate_keys(effect)
                self.assertTrue(keys and set(keys) <= set(THIRTEEN), effect)
        example = questions.parse(concern.replace("<!--", "").replace("-->", ""), source="concern.md")
        gated = [q for q in example["questions"] if questions.gate_keys(q["question"])]
        self.assertEqual([questions.gate_keys(q["question"]) for q in gated], [["prod-data"]],
                         "concern.md's example has one question that ends with (gates: <key>)")
        for text in (loop, concern):
            self.assertIn("(gates: <key>)", text)


class WaitsOnTest(unittest.TestCase):
    """C1: exactly one person per item, the gate's holder or else the loop's owner (D62, D65)."""

    def test_an_item_that_crosses_no_gate_waits_on_the_loops_owner(self):
        m = world(front="owner: ben")
        m.concern("loop/thing", concern_md(questions=["| Q1 | Which store? | C1 | The database |"]))
        item = items(m.derive(self))["loop/thing/Q1"]
        self.assertEqual((item["gate"], item["waits_on"]), (None, "ben"))

    def test_a_loop_without_an_owner_falls_back_to_section_1s_login(self):
        m = world()
        m.concern("loop/thing", concern_md(questions=["| Q1 | Which store? | C1 | The database |"]))
        item = items(m.derive(self))["loop/thing/Q1"]
        self.assertEqual(item["waits_on"], "ana", "LOOP.md §1: Ana (ana on GitHub)")

    def test_a_gated_item_waits_on_its_gates_holder_not_the_owner(self):
        m = world(front="owner: ben")
        merged(m, "[an API key rotated in production (the owner rotates it; gates: secrets)]")
        got = items(m.derive(self))["ship/staging/secrets"]
        self.assertEqual((got["gate"], got["waits_on"]), ("secrets", "carla"))

    def test_a_gate_section_2_names_no_holder_for_waits_on_the_loops_owner(self):
        m = world(front="owner: ben")
        merged(m, "[a build submitted to the beta channel (the owner submits it; gates: store), "
                  "a price change (the owner sets it; gates: money)]")
        got = items(m.derive(self))
        self.assertEqual((got["ship/staging/store"]["gate"], got["ship/staging/store"]["waits_on"]), ("store", "ben"))
        self.assertEqual((got["ship/staging/money"]["gate"], got["ship/staging/money"]["waits_on"]), ("money", "ben"),
                         "a holder that is still a placeholder is no holder")
        m = world()
        merged(m, "[a build submitted to the beta channel (the owner submits it; gates: store)]")
        self.assertEqual(items(m.derive(self))["ship/staging/store"]["waits_on"], "ana", "and §1's, with no owner:")

    def test_an_owner_written_with_an_at_sign_is_the_same_login(self):
        m = world(front="owner: '@ben'")
        m.concern("loop/thing", concern_md(questions=["| Q1 | Which store? | C1 | The database |"]))
        self.assertEqual(items(m.derive(self))["loop/thing/Q1"]["waits_on"], "ben")

    def test_with_no_owner_anywhere_an_item_waits_on_no_one_and_drift_says_why(self):
        m = world(loop_md=KEYED.replace("Ana (ana on GitHub)", "Ana"))
        m.concern("loop/thing", concern_md(questions=["| Q1 | Which store? | C1 | The database |"]))
        doc = m.derive(self)
        self.assertIsNone(items(doc)["loop/thing/Q1"]["waits_on"], "never guessed")
        lines = drift(doc, "LOOP.md, §1")
        self.assertEqual(len(lines), 1, doc["drift"])
        self.assertIn("loop", lines[0]["finding"])
        m.loop("loop", front="owner: ben")
        doc = m.derive(self)
        self.assertEqual(items(doc)["loop/thing/Q1"]["waits_on"], "ben")
        self.assertEqual(drift(doc, "LOOP.md, §1"), [], "every loop names its owner, so §1's is not needed")

    def test_an_owner_or_member_that_is_not_a_login_is_drift(self):
        m = world(front="owner: <login>\nmembers: [carla, Dan Smith]")
        m.concern("loop/thing", concern_md(questions=["| Q1 | Which store? | C1 | The database |"]))
        doc = m.derive(self)
        item = items(doc)["loop/thing/Q1"]
        self.assertEqual((item["waits_on"], item["visible_to"]), ("ana", ["carla"]))
        findings = [d["finding"] for d in drift(doc, "docs/loops/loop/README.md, front matter")]
        self.assertEqual(len(findings), 2, findings)
        self.assertTrue(any("<login>" in f for f in findings) and any("Dan Smith" in f for f in findings), findings)

    def test_an_item_that_spans_loops_waits_on_their_owner_or_else_section_1s(self):
        for fronts, expected in (((None, None), "ana"), (("owner: ben", "owner: ben"), "ben"),
                                 (("owner: ben", "owner: carla"), "ana")):
            m = world()
            for loop_id, front in zip(("loop", "other"), fronts):
                if front:
                    m.loop(loop_id, front=front)
            m.land("loop/thing", 1)
            m.concern("loop/thing", concern_md(effects="[a note]"))
            m.land("other/thing", 2)
            m.concern("other/thing", concern_md(effects="[a note]"))
            m.files["LOOP.md"] = NO_KEYS
            doc = m.derive(self)
            ship = items(doc)["ship/staging"]
            with self.subTest(fronts=fronts):
                self.assertIsNone(ship["loop"])
                self.assertEqual(ship["waits_on"], expected)


    def test_a_proof_waits_on_whom_its_needs_segment_names(self):
        """command-center/D74: a login, owner, or a gate's holder; a key §2 does not define leaves it with the owner."""
        for who, expected in (("dan", ("dan", None)), ("owner", ("ben", None)), ("gate:secrets", ("carla", "secrets")),
                              ("gate:nothing", ("ben", None))):
            m = world(front="owner: ben")
            m.land("loop/thing", 1)
            m.serve("staging")
            m.concern("loop/thing", concern_md(evidence=[
                "- 2026-10-10 · C1 · UNPROVEN · rung 1 · staging @%s · no key here · needs %s: a key" % (m.main[:7], who)]))
            item = items(m.derive(self))["loop/thing/C1"]
            with self.subTest(who=who):
                self.assertEqual((item["waits_on"], item["gate"]), expected)

class VisibleToTest(unittest.TestCase):
    """C2: the loop's members see every item of their loop, and the board says who each item waits on (D10)."""

    def test_every_item_of_a_loop_is_visible_to_its_members(self):
        m = world(front="owner: ben\nmembers: [carla, dan]")
        m.concern("loop/asked", concern_md(questions=["| Q1 | Which store? | C1 | The database |"]))
        m.concern("loop/review", concern_md())
        m.pr("loop/review", 2, "OPEN", body=PROOF.replace("loop/thing", "loop/review"))
        merged(m, "[an API key rotated in production (the owner rotates it; gates: secrets)]", number=3)
        doc = m.derive(self)
        self.assertEqual(sorted(i["kind"] for i in doc["queue"]), ["question", "review", "ship", "ship"])
        for item in doc["queue"]:
            self.assertEqual(item["visible_to"], ["carla", "dan"], item["id"])
        m = world(front="owner: ben")
        m.concern("loop/asked", concern_md(questions=["| Q1 | Which store? | C1 | The database |"]))
        self.assertEqual(items(m.derive(self))["loop/asked/Q1"]["visible_to"], [], "no members:, no one else")


class LoopPeopleTest(unittest.TestCase):
    """status-people C1: each loop names its owner and members, as the addressing step resolves them (D70, D62)."""

    def people(self, doc):
        check_document(self, doc)
        return {l["id"]: (l["owner"], l["members"]) for l in doc["loops"]}

    def test_a_loop_with_an_owner_and_members_names_them(self):
        m = world(front="owner: '@ben'\nmembers: [carla, dan, carla]")
        m.concern("loop/thing", concern_md())
        self.assertEqual(self.people(m.derive(self))["loop"], ("ben", ["carla", "dan"]))

    def test_a_loop_with_neither_names_section_1s_owner_and_no_members(self):
        m = world()
        m.concern("loop/thing", concern_md())
        self.assertEqual(self.people(m.derive(self))["loop"], ("ana", []), "LOOP.md §1: Ana (ana on GitHub)")

    def test_with_no_owner_anywhere_the_owner_is_null(self):
        m = world(loop_md=KEYED.replace("Ana (ana on GitHub)", "Ana"))
        m.concern("loop/thing", concern_md())
        self.assertEqual(self.people(m.derive(self))["loop"], (None, []), "never guessed")
        facts = m.facts()
        del facts["files"]["LOOP.md"]
        self.assertEqual(self.people(ls.derive(facts))["loop"], (None, []), "and without a LOOP.md")

    def test_an_owner_that_is_not_a_login_gives_way_to_section_1s(self):
        m = world(front="owner: <login>\nmembers: [carla, Dan Smith]")
        m.concern("loop/thing", concern_md())
        self.assertEqual(self.people(m.derive(self))["loop"], ("ana", ["carla"]))
        m = world(loop_md=KEYED.replace("Ana (ana on GitHub)", "Ana"), front="owner: <login>")
        m.concern("loop/thing", concern_md())
        self.assertEqual(self.people(m.derive(self))["loop"], (None, []))

    def test_each_loop_names_its_own(self):
        m = world(front="owner: ben\nmembers: [carla]")
        m.loop("other")
        m.concern("loop/thing", concern_md())
        m.concern("other/thing", concern_md())
        self.assertEqual(self.people(m.derive(self)), {"loop": ("ben", ["carla"]), "other": ("ana", [])})

    def test_the_board_shows_who_each_item_waits_on(self):
        m = world(front="owner: ben\nmembers: [carla]")
        m.concern("loop/asked", concern_md(questions=["| Q1 | Which store? | C1 | The database |"]))
        merged(m, "[an API key rotated in production (the owner rotates it; gates: secrets)]", number=3)
        text = ls.board(m.derive(self))
        self.assertRegex(text, r"(?m)^  \d\. question · Which store\? · .* · waits on ben$")
        self.assertRegex(text, r"(?m)^  \d\. ship · .*secrets.* · waits on carla \(gate: secrets\)")
        self.assertRegex(text, r"(?m)^  \d\. ship · Ship thing to staging · .* · waits on ben \(gate: deploy\)")
        m = world(loop_md=KEYED.replace("Ana (ana on GitHub)", "Ana"))
        m.concern("loop/asked", concern_md(questions=["| Q1 | Which store? | C1 | The database |"]))
        self.assertIn("waits on no one named", ls.board(m.derive(self)))


class GateTest(unittest.TestCase):
    """C3, with LOOP.md §2 naming keys and holders: which gate each kind of item crosses (D58, D59, D60, D63, D64)."""

    def test_a_review_crosses_merge(self):
        m = world(front="owner: ben")
        m.concern("loop/thing", concern_md())
        m.pr("loop/thing", 2, "OPEN", body=PROOF)
        review = [i for i in m.derive(self)["queue"] if i["kind"] == "review"][0]
        self.assertEqual((review["gate"], review["waits_on"]), ("merge", "ana"))

    def test_a_ship_is_one_item_per_gate_its_effects_carry_other_than_merge_plus_one_for_deploy(self):
        m = world(front="owner: ben")
        merged(m, "[an API key rotated in production (the owner rotates it; gates: secrets), "
                  "a DNS record and its certificate (the owner adds them; gates: infra, secrets), "
                  "a note for the release (gates: merge), "
                  "a feature flag turned on after the deploy (the owner turns it on; gates: deploy, hardware), "
                  "a migration on shared data]")
        doc = m.derive(self)
        ships = {i["id"]: i for i in doc["queue"] if i["kind"] == "ship"}
        self.assertEqual(sorted(ships), ["ship/staging", "ship/staging/hardware", "ship/staging/infra",
                                         "ship/staging/secrets"], "no item for merge")
        got = {k: (v["gate"], v["waits_on"], v["detail"]["manual_steps"]) for k, v in ships.items()}
        self.assertEqual(got["ship/staging"], ("deploy", "ben", [
            "a note for the release (gates: merge)",
            "a feature flag turned on after the deploy (the owner turns it on; gates: deploy, hardware)",
            "a migration on shared data"]), "deploy carries what names deploy, merge alone, or no gate")
        self.assertEqual(got["ship/staging/secrets"], ("secrets", "carla", [
            "an API key rotated in production (the owner rotates it; gates: secrets)",
            "a DNS record and its certificate (the owner adds them; gates: infra, secrets)"]))
        self.assertEqual(got["ship/staging/infra"], ("infra", "dan", [
            "a DNS record and its certificate (the owner adds them; gates: infra, secrets)"]),
            "two keys held by different people: one item for each")
        self.assertEqual(got["ship/staging/hardware"][:2], ("hardware", "erin"), "a key of the project's own")
        for item in ships.values():
            self.assertEqual((item["concerns"], item["unblocks"], item["detail"]["environment"]),
                             (["loop/thing"], ["loop/thing"], "staging"))
        self.assertEqual([d for d in doc["drift"] if "gates" in d["finding"] or "§2" in d["where"]], [])

    def test_a_ship_of_several_concerns_puts_each_on_the_gates_its_own_effects_cross(self):
        m = world(front="owner: ben")
        merged(m, "[an API key rotated in production (the owner rotates it; gates: secrets)]", ref="loop/one")
        merged(m, "[]", ref="loop/two", number=2)
        ships = {i["id"]: i for i in m.derive(self)["queue"] if i["kind"] == "ship"}
        self.assertEqual(ships["ship/staging"]["concerns"], ["loop/one", "loop/two"])
        self.assertEqual(ships["ship/staging"]["detail"]["manual_steps"], [])
        self.assertEqual(ships["ship/staging/secrets"]["concerns"], ["loop/one"])

    def test_a_refused_loop_document_pr_crosses_merge(self):
        m = world(front="owner: ben")
        m.concern("loop/thing", concern_md())
        m.pr("docs/loop-record-2026-10-20", 7, "OPEN", body="Record.\n")
        m.checks.append({"repository": "example/reports", "number": 7, "head": m.main, "ok": False,
                         "failures": ["FAIL: changes a file outside docs/loops/: src/x/a.py"], "error": None})
        item = [i for i in m.derive(self)["queue"] if i["kind"] == "refused_pr"][0]
        self.assertEqual((item["gate"], item["waits_on"]), ("merge", "ana"))

    def test_record_proof_and_contradiction_items_cross_no_gate_and_wait_on_the_loops_owner(self):
        m = world(front="owner: ben")
        m.land("loop/done", 1)
        m.land("loop/unproven", 2)
        m.land("loop/broken", 3)
        m.serve("staging")
        sha = m.main[:7]
        m.concern("loop/done", concern_md(evidence=["- 2026-10-10 · C1 · HOLDS · rung 1 · staging @%s · ran" % sha]))
        m.concern("loop/unproven", concern_md(evidence=[
            "- 2026-10-10 · C1 · UNPROVEN · rung 1 · staging @%s · needs a real phone, which only Ana has" % sha]))
        m.concern("loop/broken", concern_md(evidence=[
            "- 2026-10-10 · C1 · CONTRADICTS · rung 1 · staging @%s · p95 41 s" % sha]))
        got = {i["kind"]: (i["gate"], i["waits_on"]) for i in m.derive(self)["queue"]}
        self.assertEqual(got, {"record": (None, "ben"), "proof": (None, "ben"), "contradiction": (None, "ben")})

    def test_a_question_crosses_the_key_its_question_cell_ends_with(self):
        m = world(front="owner: ben")
        m.concern("loop/thing", concern_md(questions=[
            "| Q1 | Ship the lab build to testers? (gates: hardware) | C1 | Not yet |",
            "| Q2 | Raise the price to 12? (gates: money) | C1 | Keep 10 |",
            "| Q3 | Which store? | C1 | The database |"]))
        got = {k: (v["gate"], v["waits_on"]) for k, v in items(m.derive(self)).items()}
        self.assertEqual(got, {"loop/thing/Q1": ("hardware", "erin"), "loop/thing/Q2": ("money", "ben"),
                               "loop/thing/Q3": (None, "ben")})
        m = world()
        m.loop("loop", questions=["| Q4 | Rotate the shared key now? (gates: secrets) | `thing` | Next week |"])
        m.concern("loop/thing", concern_md())
        item = items(m.derive(self))["loop/Q4"]
        self.assertEqual((item["gate"], item["waits_on"]), ("secrets", "carla"), "a README's question too")

    def test_once_section_2_names_keys_a_key_it_does_not_define_is_drift(self):
        m = world(front="owner: ben")
        merged(m, "[an API key rotated (the owner rotates it; gates: secrts)]")
        m.concern("loop/asked", concern_md(questions=["| Q1 | Spend on a load test? (gates: spending) | C1 | No |"]))
        doc = m.derive(self)
        got = items(doc)
        self.assertNotIn("ship/staging/secrts", got, "a key §2 does not define is not a gate")
        self.assertEqual(got["ship/staging"]["detail"]["manual_steps"],
                         ["an API key rotated (the owner rotates it; gates: secrts)"], "its step is not lost")
        self.assertEqual((got["loop/asked/Q1"]["gate"], got["loop/asked/Q1"]["waits_on"]), (None, "ben"))
        effect = drift(doc, "docs/loops/loop/thing.md, effects")
        self.assertEqual(len(effect), 1, doc["drift"])
        self.assertIn("secrts", effect[0]["finding"])
        question = [d for d in doc["drift"] if d["where"].startswith("docs/loops/loop/asked.md:")]
        self.assertEqual(len(question), 1, doc["drift"])
        self.assertIn("spending", question[0]["finding"])
        self.assertRegex(question[0]["where"], r"^docs/loops/loop/asked\.md:\d+, Questions$")

    def test_a_question_that_names_two_keys_crosses_none_and_is_drift(self):
        m = world(front="owner: ben")
        m.concern("loop/thing", concern_md(questions=["| Q1 | Rotate and bill? (gates: secrets, money) | C1 | No |"]))
        doc = m.derive(self)
        item = items(doc)["loop/thing/Q1"]
        self.assertEqual((item["gate"], item["waits_on"]), (None, "ben"))
        self.assertTrue(any("one gate" in d["finding"] for d in doc["drift"] if "Questions" in d["where"]),
                        doc["drift"])

    def test_a_parked_concerns_effects_are_not_checked(self):
        m = world(front="owner: ben")
        m.concern("loop/thing", concern_md(effects="[a step (gates: nothing)]", extra="parked: D1",
                                           decisions=["| D1 | Parked. | Ana, 2026-10-01 | |"]))
        self.assertEqual(drift(m.derive(self), "docs/loops/loop/thing.md, effects"), [])


class NoKeysTest(unittest.TestCase):
    """C3 and C1 while LOOP.md §2 names no keys (D65): items keep the gate their key names and wait on the loop's
    owner, and one drift line says §2 names no keys."""

    def test_items_keep_their_gate_and_wait_on_the_loops_owner(self):
        m = world(loop_md=NO_KEYS, front="owner: ben")
        merged(m, "[an API key rotated in production (the owner rotates it; gates: secrets)]")
        m.concern("loop/asked", concern_md(questions=["| Q1 | Raise the price? (gates: money) | C1 | Keep it |"]))
        m.concern("loop/review", concern_md())
        m.pr("loop/review", 3, "OPEN", body=PROOF.replace("loop/thing", "loop/review"))
        got = {k: (v["gate"], v["waits_on"]) for k, v in items(m.derive(self)).items()}
        self.assertEqual(got, {"ship/staging": ("deploy", "ben"), "ship/staging/secrets": ("secrets", "ben"),
                               "loop/asked/Q1": ("money", "ben"), "example/reports#3": ("merge", "ben")})
        m = world(loop_md=NO_KEYS)
        merged(m, "[an API key rotated in production (the owner rotates it; gates: secrets)]")
        self.assertEqual(items(m.derive(self))["ship/staging/secrets"]["waits_on"], "ana", "§1's, with no owner:")

    def test_one_drift_line_says_section_2_names_no_keys(self):
        m = world(loop_md=NO_KEYS, front="owner: ben")
        merged(m, "[an API key rotated (gates: secrets), a step (gates: lab)]")
        m.concern("loop/asked", concern_md(questions=["| Q1 | Raise the price? (gates: money) | C1 | Keep it |"]))
        doc = m.derive(self)
        lines = drift(doc, "LOOP.md, §2")
        self.assertEqual(len(lines), 1, doc["drift"])
        self.assertIn("names no gate keys", lines[0]["finding"])
        self.assertEqual([d for d in doc["drift"] if "gates" in d["finding"]], [], "no line per item")
        got = items(doc)
        self.assertNotIn("ship/staging/lab", got, "a key outside the thirteen is not a gate")
        self.assertEqual(got["ship/staging"]["detail"]["manual_steps"], ["a step (gates: lab)"])

    def test_once_section_2_names_a_key_the_line_goes(self):
        m = world(loop_md=NO_KEYS.replace("  - Money:", "  - **Money** (key: money; holder: ben):"))
        merged(m, "[an API key rotated (the owner rotates it; gates: secrets)]")
        doc = m.derive(self)
        self.assertEqual(drift(doc, "LOOP.md, §2"), [])
        self.assertNotIn("ship/staging/secrets", items(doc), "§2 now names keys, and secrets is not one of them")
        self.assertEqual(len(drift(doc, "docs/loops/loop/thing.md, effects")), 1)

    def test_a_key_section_2_defines_twice_is_drift(self):
        m = world(loop_md=KEYED.replace("(key: store)", "(key: secrets; holder: ben)"))
        merged(m, "[an API key rotated (the owner rotates it; gates: secrets)]")
        doc = m.derive(self)
        self.assertEqual(items(doc)["ship/staging/secrets"]["waits_on"], "ben", "the first line wins")
        lines = drift(doc, "LOOP.md, §2")
        self.assertEqual(len(lines), 1, doc["drift"])
        self.assertIn("secrets", lines[0]["finding"])

    def test_without_loop_md_items_keep_their_gate_and_name_no_one(self):
        m = world()
        m.concern("loop/thing", concern_md(questions=["| Q1 | Raise the price? (gates: money) | C1 | Keep it |"]))
        facts = m.facts()
        del facts["files"]["LOOP.md"]
        doc = ls.derive(facts)
        check_document(self, doc)
        item = items(doc)["loop/thing/Q1"]
        self.assertEqual((item["gate"], item["waits_on"]), ("money", None))
        self.assertEqual(drift(doc, "LOOP.md, §2"), [], "missing already says there is no LOOP.md")
        self.assertEqual(len(drift(doc, "LOOP.md, §1")), 1, doc["drift"])


if __name__ == "__main__":
    unittest.main()
