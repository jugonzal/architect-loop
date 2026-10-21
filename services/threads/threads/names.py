"""The shapes of names in paths and bodies; openapi.yaml states the same patterns."""

import re

NAME = r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}"
SESSION = r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}"
LOGIN = r"[A-Za-z0-9][A-Za-z0-9-]{0,38}"
REPO = r"[A-Za-z0-9._-]{1,100}"

_full = {kind: re.compile(pattern) for kind, pattern in
         {"name": NAME, "session": SESSION, "login": LOGIN, "repo": REPO}.items()}


def valid(kind, value):
    return isinstance(value, str) and _full[kind].fullmatch(value) is not None
