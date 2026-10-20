"""Tests for plugin/skills/loop-status/scripts/status.schema.json, the status document that the loop-status
script writes with --json, the status service serves and the app reads (command-center/status-api).

- C1: the schema validates every fixture in tests/fixtures/status/, and rejects a document missing a required
  field. Every required field the schema declares is removed from a fixture in turn, and each removal must fail.
- C2: the fixtures cover every state in the derivation table of loop-status's SKILL.md, plus unknown. The states
  are read from the table itself, so the table, the schema and the fixtures cannot drift apart.

The tests use only the standard library (LOOP.md §4), so they carry a small validator for the subset of JSON
Schema (draft 2020-12) that the schema uses. The validator refuses any keyword outside that subset, so the schema
cannot rely on one it would silently ignore, and ValidatorTest checks each keyword it supports.

Run from the repository root: python3 -m unittest discover -s tests -v
"""

import copy
import glob
import json
import math
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_DIR = os.path.join(ROOT, "plugin", "skills", "loop-status")
SCHEMA = os.path.join(SKILL_DIR, "scripts", "status.schema.json")
SKILL = os.path.join(SKILL_DIR, "SKILL.md")
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "status")


# --- A validator for the subset of JSON Schema the status schema uses --------------------------------------------

ANNOTATIONS = {"$schema", "$id", "$comment", "$defs", "title", "description"}
ASSERTIONS = {"$ref", "type", "enum", "const", "properties", "required", "additionalProperties", "items",
              "minItems", "uniqueItems", "minLength", "pattern", "minimum", "maximum", "oneOf"}
TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_type(value, name):
    if name == "object":
        return isinstance(value, dict)
    if name == "array":
        return isinstance(value, list)
    if name == "string":
        return isinstance(value, str)
    if name == "boolean":
        return isinstance(value, bool)
    if name == "null":
        return value is None
    if name == "number":
        return is_number(value)
    if name == "integer":
        return is_number(value) and (isinstance(value, int) or (math.isfinite(value) and value.is_integer()))
    raise ValueError("unknown type %r" % name)


def json_equal(a, b):
    """Equality as JSON Schema defines it: true is not 1, and 1 is 1.0."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if is_number(a) and is_number(b):
        return a == b
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(json_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(json_equal(a[k], b[k]) for k in a)
    return type(a) is type(b) and a == b


def show(path):
    out = "$"
    for part in path:
        out += "[%d]" % part if isinstance(part, int) else "." + part
    return out


class Validator:
    """Validates an instance against a schema written in the supported subset.

    errors(instance) lists what is wrong, each prefixed with the instance path. required_seen(instance) lists
    (schema pointer, field, instance path) for every required field the instance satisfied, counting only the
    oneOf branch that matched, so a test can remove each one and expect a failure.
    """

    def __init__(self, schema):
        self.schema = schema

    def errors(self, instance):
        errors, seen = [], []
        self._check(instance, self.schema, "#", (), errors, seen)
        return errors

    def required_seen(self, instance):
        errors, seen = [], []
        self._check(instance, self.schema, "#", (), errors, seen)
        if errors:
            raise AssertionError("not valid: %s" % errors)
        return seen

    def resolve(self, ref):
        if not ref.startswith("#/"):
            raise ValueError("only local references are supported: %r" % ref)
        node = self.schema
        for part in ref[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            if not isinstance(node, dict) or part not in node:
                raise ValueError("unresolvable reference %r" % ref)
            node = node[part]
        return node

    def subschemas(self):
        """Every schema node, with its pointer, so that nothing unreachable escapes the keyword check."""
        out = []

        def walk(node, ptr):
            if isinstance(node, bool):
                return
            if not isinstance(node, dict):
                raise ValueError("%s: a schema must be an object or a boolean" % ptr)
            out.append((ptr, node))
            for key, sub in node.get("properties", {}).items():
                walk(sub, "%s/properties/%s" % (ptr, key))
            for key, sub in node.get("$defs", {}).items():
                walk(sub, "%s/$defs/%s" % (ptr, key))
            for i, sub in enumerate(node.get("oneOf", [])):
                walk(sub, "%s/oneOf/%d" % (ptr, i))
            for key in ("items", "additionalProperties"):
                if key in node:
                    walk(node[key], "%s/%s" % (ptr, key))

        walk(self.schema, "#")
        return out

    def check_schema(self):
        """Raise if the schema uses a keyword this validator does not implement, or a reference that is broken."""
        for ptr, node in self.subschemas():
            unknown = set(node) - ANNOTATIONS - ASSERTIONS
            if unknown:
                raise ValueError("%s: unsupported keywords %s" % (ptr, sorted(unknown)))
            types = node.get("type", [])
            for name in types if isinstance(types, list) else [types]:
                if name not in TYPES:
                    raise ValueError("%s: unknown type %r" % (ptr, name))
            if "$ref" in node:
                self.resolve(node["$ref"])
            if "pattern" in node:
                re.compile(node["pattern"])

    def _check(self, value, schema, ptr, path, errors, seen):
        if schema is True:
            return
        if schema is False:
            errors.append("%s: no value is allowed here" % show(path))
            return
        unknown = set(schema) - ANNOTATIONS - ASSERTIONS
        if unknown:
            raise ValueError("%s: unsupported keywords %s" % (ptr, sorted(unknown)))

        if "$ref" in schema:
            self._check(value, self.resolve(schema["$ref"]), schema["$ref"], path, errors, seen)

        if "type" in schema:
            types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
            if not any(is_type(value, name) for name in types):
                errors.append("%s: expected %s, got %s" % (show(path), " or ".join(types), json.dumps(value)[:60]))
        if "enum" in schema and not any(json_equal(value, option) for option in schema["enum"]):
            errors.append("%s: %s is not one of %s" % (show(path), json.dumps(value), schema["enum"]))
        if "const" in schema and not json_equal(value, schema["const"]):
            errors.append("%s: %s is not %s" % (show(path), json.dumps(value), json.dumps(schema["const"])))

        if isinstance(value, str):
            if "minLength" in schema and len(value) < schema["minLength"]:
                errors.append("%s: shorter than %d characters" % (show(path), schema["minLength"]))
            if "pattern" in schema and not re.search(schema["pattern"], value):
                errors.append("%s: %s does not match %s" % (show(path), json.dumps(value), schema["pattern"]))

        if is_number(value):
            if "minimum" in schema and value < schema["minimum"]:
                errors.append("%s: %s is less than %s" % (show(path), value, schema["minimum"]))
            if "maximum" in schema and value > schema["maximum"]:
                errors.append("%s: %s is more than %s" % (show(path), value, schema["maximum"]))

        if isinstance(value, list):
            if "minItems" in schema and len(value) < schema["minItems"]:
                errors.append("%s: fewer than %d items" % (show(path), schema["minItems"]))
            if schema.get("uniqueItems"):
                for i in range(len(value)):
                    for j in range(i):
                        if json_equal(value[i], value[j]):
                            errors.append("%s: items %d and %d are equal" % (show(path), j, i))
            if "items" in schema:
                for i, item in enumerate(value):
                    self._check(item, schema["items"], ptr + "/items", path + (i,), errors, seen)

        if isinstance(value, dict):
            for field in schema.get("required", []):
                if field in value:
                    seen.append((ptr, field, path))
                else:
                    errors.append("%s: missing required field '%s'" % (show(path), field))
            properties = schema.get("properties", {})
            for field, sub in properties.items():
                if field in value:
                    self._check(value[field], sub, "%s/properties/%s" % (ptr, field), path + (field,), errors, seen)
            extra = schema.get("additionalProperties", True)
            for field in value:
                if field in properties:
                    continue
                if extra is False:
                    errors.append("%s: unexpected field '%s'" % (show(path), field))
                elif extra is not True:
                    self._check(value[field], extra, ptr + "/additionalProperties", path + (field,), errors, seen)

        if "oneOf" in schema:
            matched, failures = [], []
            for i, branch in enumerate(schema["oneOf"]):
                branch_errors, branch_seen = [], []
                self._check(value, branch, "%s/oneOf/%d" % (ptr, i), path, branch_errors, branch_seen)
                if branch_errors:
                    failures.extend(branch_errors)
                else:
                    matched.append(branch_seen)
            if len(matched) == 1:
                seen.extend(matched[0])
            else:
                errors.append("%s: matches %d of the %d schemas in %s/oneOf, not exactly one" % (
                    show(path), len(matched), len(schema["oneOf"]), ptr))
                if not matched:
                    errors.extend(failures)


# --- Helpers ------------------------------------------------------------------------------------------------------

def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fixture_paths():
    return sorted(glob.glob(os.path.join(FIXTURES, "*.json")))


def fixtures():
    return [(os.path.basename(p), load(p)) for p in fixture_paths()]


def concerns_of(doc):
    for loop in doc["loops"]:
        for concern in loop["concerns"]:
            yield loop, concern


def derivation_table_states(text):
    """The first column of the derivation table in loop-status's step 4, in order."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^\s*\|\s*State\s*\|\s*When \(facts\)\s*\|\s*Next\s*\|\s*$", line):
            break
    else:
        raise AssertionError("no '| State | When (facts) | Next |' table in %s" % SKILL)
    if not re.match(r"^\s*\|[\s|:-]+\|\s*$", lines[i + 1]):
        raise AssertionError("the derivation table's header is not followed by a separator row")
    states = []
    for line in lines[i + 2:]:
        if not line.strip().startswith("|"):
            break
        states.append(line.strip().split("|")[1].strip())
    return states


def loop_states_in_step_5(text):
    """The bold state names in step 5, 'Derive each loop's state'."""
    match = re.search(r"^5\. \*\*Derive each loop's state\.\*\*(.*?)^\d+\. \*\*", text, re.M | re.S)
    if not match:
        raise AssertionError("no step 5 'Derive each loop's state' in %s" % SKILL)
    return re.findall(r"\*\*([a-z]+)\*\*", match.group(1))


# --- The validator itself ----------------------------------------------------------------------------------------

class ValidatorTest(unittest.TestCase):
    """Each supported keyword accepts what it should and rejects what it should, so C1's proof is not hollow."""

    def assertValid(self, schema, value):
        self.assertEqual(Validator(schema).errors(value), [], json.dumps(value))

    def assertInvalid(self, schema, value):
        self.assertNotEqual(Validator(schema).errors(value), [], json.dumps(value))

    def test_type(self):
        self.assertValid({"type": "integer"}, 3)
        self.assertValid({"type": "integer"}, 3.0)
        self.assertInvalid({"type": "integer"}, 3.5)
        self.assertInvalid({"type": "integer"}, True)
        self.assertInvalid({"type": "number"}, False)
        self.assertInvalid({"type": "string"}, None)
        self.assertValid({"type": ["string", "null"]}, None)
        self.assertInvalid({"type": ["string", "null"]}, 0)
        self.assertInvalid({"type": "object"}, [])
        self.assertInvalid({"type": "array"}, {})
        self.assertValid({"type": "boolean"}, False)

    def test_enum_and_const_use_json_equality(self):
        self.assertValid({"enum": ["a", "b"]}, "b")
        self.assertInvalid({"enum": ["a", "b"]}, "c")
        self.assertValid({"const": 1}, 1.0)
        self.assertInvalid({"const": 1}, True)
        self.assertInvalid({"const": 1}, "1")

    def test_required(self):
        schema = {"type": "object", "required": ["a"]}
        self.assertValid(schema, {"a": None})
        self.assertInvalid(schema, {"b": 1})
        self.assertIn("missing required field 'a'", Validator(schema).errors({})[0])

    def test_properties_and_additional_properties(self):
        schema = {"type": "object", "properties": {"a": {"type": "string"}}, "additionalProperties": False}
        self.assertValid(schema, {"a": "x"})
        self.assertInvalid(schema, {"a": 1})
        self.assertInvalid(schema, {"a": "x", "b": 1})
        self.assertValid({"type": "object", "properties": {}, "additionalProperties": True}, {"b": 1})
        self.assertInvalid({"type": "object", "additionalProperties": {"type": "string"}}, {"b": 1})

    def test_items_min_items_and_unique_items(self):
        schema = {"type": "array", "items": {"type": "string"}, "minItems": 1, "uniqueItems": True}
        self.assertValid(schema, ["a", "b"])
        self.assertInvalid(schema, [])
        self.assertInvalid(schema, ["a", 1])
        self.assertInvalid(schema, ["a", "a"])
        self.assertValid({"uniqueItems": True}, [1, True])

    def test_strings(self):
        self.assertValid({"minLength": 1}, "x")
        self.assertInvalid({"minLength": 1}, "")
        self.assertValid({"pattern": "^[0-9a-f]{7,40}$"}, "abc1234")
        self.assertInvalid({"pattern": "^[0-9a-f]{7,40}$"}, "abc123")
        self.assertValid({"pattern": "b"}, "abc")  # unanchored, as JSON Schema says
        self.assertValid({"type": ["string", "null"], "pattern": "^x$"}, None)

    def test_numbers(self):
        self.assertValid({"minimum": 1, "maximum": 6}, 6)
        self.assertInvalid({"minimum": 1, "maximum": 6}, 0)
        self.assertInvalid({"minimum": 1, "maximum": 6}, 7)

    def test_ref(self):
        schema = {"$defs": {"sha": {"type": "string", "pattern": "^[0-9a-f]+$"}},
                  "type": "array", "items": {"$ref": "#/$defs/sha"}}
        self.assertValid(schema, ["abc"])
        self.assertInvalid(schema, ["xyz"])
        with self.assertRaises(ValueError):
            Validator({"$ref": "#/$defs/missing"}).errors(1)

    def test_one_of_needs_exactly_one_match(self):
        schema = {"oneOf": [{"type": "string"}, {"minLength": 2}]}
        self.assertValid(schema, "a")
        self.assertInvalid(schema, "ab")
        self.assertValid(schema, 1.5)  # minLength ignores numbers, so only the second branch matches
        self.assertInvalid({"oneOf": [{"type": "string"}, {"type": "null"}]}, 1)

    def test_one_of_reports_why_no_branch_matched(self):
        schema = {"oneOf": [{"type": "object", "required": ["question"]}, {"type": "object", "required": ["pr"]}]}
        errors = Validator(schema).errors({})
        self.assertTrue(any("'question'" in e for e in errors), errors)

    def test_required_seen_counts_only_the_matching_branch(self):
        schema = {"oneOf": [{"required": ["a"], "properties": {"k": {"const": 1}}},
                            {"required": ["b"], "properties": {"k": {"const": 2}}}]}
        seen = Validator(schema).required_seen({"k": 2, "a": 0, "b": 0})
        self.assertEqual([(ptr, field) for ptr, field, _ in seen], [("#/oneOf/1", "b")])

    def test_unsupported_keywords_are_refused(self):
        with self.assertRaises(ValueError):
            Validator({"type": "object", "patternProperties": {}}).errors({})
        with self.assertRaises(ValueError):
            Validator({"$defs": {"x": {"anyOf": []}}}).check_schema()
        with self.assertRaises(ValueError):
            Validator({"type": "int"}).check_schema()


# --- C1: the schema --------------------------------------------------------------------------------------------

class SchemaTest(unittest.TestCase):
    """C1: a versioned schema that validates the fixtures and rejects a document missing a required field."""

    @classmethod
    def setUpClass(cls):
        cls.schema = load(SCHEMA)
        cls.validator = Validator(cls.schema)
        cls.fixtures = fixtures()

    def test_schema_uses_only_what_the_validator_implements(self):
        self.validator.check_schema()

    def test_schema_is_versioned(self):
        version = self.schema["properties"]["schema_version"]
        self.assertEqual(version["type"], "integer")
        self.assertIsInstance(version["const"], int)
        self.assertIn("schema_version", self.schema["required"])

    def test_schema_carries_what_c1_lists(self):
        defs = self.schema["$defs"]
        self.assertTrue({"project", "loops", "queue", "agents_can_start"} <= set(self.schema["required"]))
        self.assertTrue({"state", "reason", "inputs"} <= set(defs["concern"]["required"]))
        self.assertTrue({"kind", "unblocks", "waits_on", "visible_to"} <= set(defs["queue_item"]["required"]))
        self.assertEqual(defs["queue_kind"]["enum"], ["question", "review", "ship", "record"])
        branches = [b["properties"]["kind"]["const"] for b in defs["queue_item"]["oneOf"]]
        self.assertEqual(branches, defs["queue_kind"]["enum"], "one detail shape per queue kind")

    def test_there_are_fixtures(self):
        self.assertGreaterEqual(len(self.fixtures), 2)

    def test_every_fixture_validates(self):
        for name, doc in self.fixtures:
            with self.subTest(fixture=name):
                self.assertEqual(self.validator.errors(doc), [])

    def test_removing_any_required_field_fails(self):
        """For every required field the fixtures exercise, a copy of the fixture without it is rejected."""
        tried = set()
        for name, doc in self.fixtures:
            for ptr, field, path in self.validator.required_seen(doc):
                if (ptr, field) in tried:
                    continue
                tried.add((ptr, field))
                broken = copy.deepcopy(doc)
                node = broken
                for part in path:
                    node = node[part]
                del node[field]
                with self.subTest(fixture=name, field=show(path + (field,))):
                    errors = self.validator.errors(broken)
                    self.assertTrue(any("'%s'" % field in e for e in errors), errors)
        self.assertGreater(len(tried), 50)

    def test_the_fixtures_exercise_every_required_field(self):
        """So the removal test above covers the whole schema, and the app has an example of every shape."""
        declared = {(ptr, field) for ptr, node in self.validator.subschemas() for field in node.get("required", [])}
        exercised = {(ptr, field) for _, doc in self.fixtures for ptr, field, _ in self.validator.required_seen(doc)}
        self.assertEqual(declared - exercised, set())

    def test_rejects_states_the_derivation_does_not_produce(self):
        """Per command-center/D5, 'proving' and 'in review' are reasons, never states."""
        _, doc = self.board()
        for state in ("proving", "review", "Unknown", ""):
            broken = copy.deepcopy(doc)
            broken["loops"][0]["concerns"][0]["state"] = state
            with self.subTest(state=state):
                self.assertNotEqual(self.validator.errors(broken), [])

    def test_rejects_a_queue_item_whose_detail_does_not_match_its_kind(self):
        _, doc = self.board()
        broken = copy.deepcopy(doc)
        review = next(item for item in broken["queue"] if item["kind"] == "review")
        review["kind"] = "question"
        errors = self.validator.errors(broken)
        self.assertTrue(any("not exactly one" in e for e in errors), errors)

    def test_rejects_malformed_documents(self):
        _, doc = self.board()
        cases = {
            "an unexpected field": lambda d: d.update(extra=1),
            "a status field on a loop": lambda d: d["loops"][0].update(status="active"),
            "another schema version": lambda d: d.update(
                schema_version=self.schema["properties"]["schema_version"]["const"] + 1),
            "an environment with neither a commit nor an error": lambda d: d["environments"][0].update(served=None),
            "a branch name for a commit": lambda d: d["main"].update(sha="main"),
            "a local time for as_of": lambda d: d.update(as_of="2026-10-20 15:00"),
            "rung 7": lambda d: d["loops"][0]["concerns"][0]["claims"][0]["evidence"][0].update(rung=7),
            "two people waited on": lambda d: d["queue"][0].update(waits_on=["ana", "ben"]),
        }
        for case, mutate in cases.items():
            broken = copy.deepcopy(doc)
            mutate(broken)
            with self.subTest(case=case):
                self.assertNotEqual(self.validator.errors(broken), [])

    def board(self):
        return next((n, d) for n, d in self.fixtures if d["queue"])


# --- C2: the fixtures cover the derivation's states ---------------------------------------------------------------

class StateCoverageTest(unittest.TestCase):
    """C2: the fixtures hold every state in loop-status's derivation table, plus unknown, and nothing else."""

    @classmethod
    def setUpClass(cls):
        with open(SKILL, encoding="utf-8") as f:
            cls.skill = f.read()
        cls.schema = load(SCHEMA)
        cls.fixtures = fixtures()

    def table_states(self):
        self.assertIn("**Unknown is a state too.**", self.skill, "SKILL.md no longer makes unknown a state")
        return derivation_table_states(self.skill) + ["unknown"]

    def test_the_table_is_read(self):
        states = derivation_table_states(self.skill)
        self.assertGreaterEqual(len(states), 10)
        self.assertEqual(len(states), len(set(states)))

    def test_the_schema_has_exactly_the_tables_states(self):
        self.assertEqual(self.schema["$defs"]["concern_state"]["enum"], self.table_states())

    def test_the_fixtures_cover_every_state_and_no_other(self):
        found = {concern["state"] for _, doc in self.fixtures for _, concern in concerns_of(doc)}
        expected = set(self.table_states())
        self.assertEqual(sorted(expected - found), [], "states in the table with no fixture")
        self.assertEqual(sorted(found - expected), [], "states in the fixtures that the table does not have")

    def test_the_schema_and_fixtures_have_exactly_step_5s_loop_states(self):
        expected = loop_states_in_step_5(self.skill) + ["unknown"]
        self.assertEqual(sorted(self.schema["$defs"]["loop_state"]["enum"]), sorted(expected))
        found = {loop["state"] for _, doc in self.fixtures for loop in doc["loops"]}
        self.assertEqual(found, set(expected))

    def test_the_fixtures_cover_every_queue_kind_start_action_and_verdict(self):
        defs = self.schema["$defs"]
        kinds = {item["kind"] for _, doc in self.fixtures for item in doc["queue"]}
        actions = {item["action"] for _, doc in self.fixtures for item in doc["agents_can_start"]}
        verdicts = {line["verdict"] for _, doc in self.fixtures for _, concern in concerns_of(doc)
                    for claim in concern["claims"] for line in claim["evidence"]}
        self.assertEqual(kinds, set(defs["queue_kind"]["enum"]))
        self.assertEqual(actions, set(defs["start"]["properties"]["action"]["enum"]))
        self.assertEqual(verdicts, set(defs["verdict"]["enum"]))

    def test_an_unknown_concern_names_the_missing_fact(self):
        unknown = [c for _, doc in self.fixtures for _, c in concerns_of(doc) if c["state"] == "unknown"]
        self.assertTrue(unknown)
        for concern in unknown:
            self.assertTrue(concern["inputs"].get("missing"), concern["id"])


class FixtureCoherenceTest(unittest.TestCase):
    """The fixtures are boards a derivation could produce, so the app can be built against them."""

    @classmethod
    def setUpClass(cls):
        cls.fixtures = fixtures()

    def test_references_resolve(self):
        for name, doc in self.fixtures:
            concerns = {"%s/%s" % (loop["id"], c["id"]) for loop, c in concerns_of(doc)}
            loops = {loop["id"] for loop in doc["loops"]}
            environments = {env["name"] for env in doc["environments"]}
            with self.subTest(fixture=name):
                self.assertEqual(len(concerns), sum(1 for _ in concerns_of(doc)), "duplicate concern ids")
                for item in doc["queue"]:
                    self.assertTrue(set(item["concerns"]) | set(item["unblocks"]) <= concerns, item["id"])
                    self.assertTrue(item["loop"] is None or item["loop"] in loops, item["id"])
                for item in doc["agents_can_start"]:
                    self.assertIn(item["concern"], concerns)
                for _, concern in concerns_of(doc):
                    ships_to = concern["contract"]["ships_to"]
                    self.assertTrue(ships_to is None or ships_to in environments, concern["id"])
                    self.assertEqual(concern["inputs"]["served"]["environment"], ships_to, concern["id"])
                    self.assertEqual(concern["inputs"]["main"], doc["main"]["sha"], concern["id"])
                self.assertEqual(len({item["id"] for item in doc["queue"]}), len(doc["queue"]), "duplicate ids")

    def test_the_queue_is_sorted_most_unblocking_first(self):
        for name, doc in self.fixtures:
            counts = [len(item["unblocks"]) for item in doc["queue"]]
            self.assertEqual(counts, sorted(counts, reverse=True), name)


if __name__ == "__main__":
    unittest.main()
