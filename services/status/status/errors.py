"""Errors that the API turns into answers."""


class InvalidCredentials(Exception):
    """The caller sent no token, or one GitHub does not accept (401)."""


class Unavailable(Exception):
    """GitHub cannot be reached or does not answer as expected, or the service's app cannot get a token, so the
    caller cannot be checked or main cannot be read (503). Nothing older is served instead."""
