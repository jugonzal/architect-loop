"""Errors that the API turns into answers."""


class InvalidCredentials(Exception):
    """The caller sent no token, or one that neither GitHub nor the service-identity check accepts (401)."""


class Unavailable(Exception):
    """GitHub, or Google's key set, could not be reached, so the caller cannot be checked (503)."""
