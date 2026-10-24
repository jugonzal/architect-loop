"""Errors that the API turns into answers, and the ones the poller logs."""


class InvalidCredentials(Exception):
    """The caller sent no token, or one GitHub does not accept (401)."""


class Unavailable(Exception):
    """GitHub, the status service, the metadata server or Expo cannot be reached or does not answer as expected (503
    for a caller; for the poller, nothing is pushed from that read)."""
