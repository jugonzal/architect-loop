"""GitHub's deliveries to threads' own app: review comments mirrored into concern threads (command-center/D6, D27).

A pull request names its concern with a `Concern: <loop>/<concern>` line in its body, as every concern's pull
request does (LOOP.md §6). The head branch is not used: `docs/<loop>-<topic>` and other branches have the same
shape as `<loop>/<concern>`, and this service does not read the repository to tell them apart.
"""

import hashlib
import hmac
import re

from .names import NAME

CONCERN_LINE = re.compile(rf"^Concern:[ \t]*({NAME})/({NAME})[ \t]*\r?$", re.MULTILINE)


def signature_ok(secret, body, header):
    """True when `header` is GitHub's X-Hub-Signature-256 for `body` under `secret`."""
    if not secret or not header or not header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)


def concerns_named(pull_request):
    body = (pull_request or {}).get("body") or ""
    seen = []
    for loop, concern in CONCERN_LINE.findall(body):
        if (loop, concern) not in seen:
            seen.append((loop, concern))
    return seen


def mirrors(event, payload):
    """What a delivery asks to mirror: (project, [(loop, concern)], message fields), or None to ignore it."""
    if not isinstance(payload, dict):
        return None
    project = ((payload.get("repository") or {}).get("full_name"))
    action = payload.get("action")
    if event == "pull_request_review_comment" and action == "created":
        item, source_type = payload.get("comment") or {}, "github_review_comment"
        path, state = item.get("path"), None
    elif event == "pull_request_review" and action == "submitted":
        item, source_type = payload.get("review") or {}, "github_review"
        path, state = None, item.get("state")
    else:
        return None
    body = item.get("body")
    if not project or not isinstance(body, str) or not body.strip() or item.get("id") is None:
        return None
    pull_request = payload.get("pull_request") or {}
    concerns = concerns_named(pull_request)
    if not concerns or not isinstance(pull_request.get("number"), int):
        return None
    message = {
        "body": body,
        "login": (item.get("user") or {}).get("login") or "ghost",
        "association": item.get("author_association"),
        "source": {
            "type": source_type,
            "id": str(item["id"]),
            "url": item.get("html_url") or pull_request.get("html_url") or "",
            "pull_request": pull_request.get("number"),
            "path": path,
            "review_state": state,
        },
    }
    return project, concerns, message
