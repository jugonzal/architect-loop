"""Call the runner's WSGI app in process and check every answer against services/runner/openapi.yaml (C1, D29)."""

import io
import json
import os
import re
import urllib.parse
from wsgiref.util import setup_testing_defaults

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

SERVICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(SERVICE, "openapi.yaml")) as _f:
    SPEC = yaml.safe_load(_f)

_URN = "urn:architect-loop:runner-openapi"
_REGISTRY = Registry().with_resource(_URN, Resource.from_contents(SPEC, default_specification=DRAFT202012))


def _pointer(*parts):
    return "/".join(str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def _template_regex(template):
    return re.compile("^" + re.sub(r"\\\{[^}]+\\\}", "[^/]+", re.escape(template)) + "$")


TEMPLATES = [(t, _template_regex(t)) for t in SPEC["paths"]]


def template_for(path):
    for template, regex in TEMPLATES:
        if regex.match(path):
            return template
    return None


def documented():
    """Every (method, path template, status) the spec documents."""
    for template, item in SPEC["paths"].items():
        for method, op in item.items():
            for status in op["responses"]:
                yield method.upper(), template, int(status)


def validator(pointer):
    return Draft202012Validator({"$ref": f"{_URN}#{pointer}"}, registry=_REGISTRY, format_checker=FormatChecker())


def response_schema_pointer(method, template, status):
    op = SPEC["paths"][template][method.lower()]
    response = op["responses"].get(str(status))
    if response is None:
        return None
    if "$ref" in response:
        base = response["$ref"].lstrip("#")
        response = SPEC
        for part in base.strip("/").split("/"):
            response = response[part]
    else:
        base = "/" + _pointer("paths", template, method.lower(), "responses", str(status))
    return base + "/" + _pointer("content", "application/json", "schema")


def request_schema_pointer(method, template):
    return "/" + _pointer("paths", template, method.lower(), "requestBody", "content", "application/json", "schema")


class Response:
    def __init__(self, status, headers, body):
        self.status, self.headers, self.raw = status, headers, body
        self.json = json.loads(body) if body else None

    def __repr__(self):
        return f"<{self.status} {self.raw[:300]!r}>"


class ContractClient:
    """Calls the app and fails the test on any answer the spec does not describe."""

    exercised = set()

    def __init__(self, testcase, app):
        self.testcase, self.app = testcase, app

    def call(self, method, path, body=None, token=None, query=None, raw=None):
        environ = {}
        setup_testing_defaults(environ)
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else b"")
        environ.update({
            "REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": urllib.parse.urlencode(query or {}),
            "CONTENT_LENGTH": str(len(data)), "CONTENT_TYPE": "application/json", "wsgi.input": io.BytesIO(data),
        })
        if token:
            environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        captured = {}

        def start_response(status, headers, exc_info=None):
            captured["status"], captured["headers"] = int(status.split()[0]), dict(headers)

        out = b"".join(self.app(environ, start_response))
        response = Response(captured["status"], captured["headers"], out.decode())
        self.check(method, path, response)
        return response

    def check(self, method, path, response):
        template = template_for(path)
        if template is None or method.lower() not in SPEC["paths"][template]:
            return  # outside the API: only the spec's operations are its contract
        pointer = response_schema_pointer(method, template, response.status)
        self.testcase.assertIsNotNone(
            pointer, f"{method} {template} answered {response.status}, which openapi.yaml does not document: {response}")
        self.testcase.assertEqual(response.headers.get("Content-Type"), "application/json")
        errors = sorted(validator(pointer).iter_errors(response.json), key=lambda e: list(e.path))
        self.testcase.assertFalse(errors, f"{method} {template} {response.status} does not match openapi.yaml: "
                                          + "; ".join(f"{list(e.path)}: {e.message}" for e in errors[:5]))
        ContractClient.exercised.add((method, template, response.status))


def request_errors(method, template, body):
    """Why a request body does not match the spec, or [] when it does."""
    return [e.message for e in validator(request_schema_pointer(method, template)).iter_errors(body)]
