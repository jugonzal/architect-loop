"""The runner's Cloud Run service identity (command-center/D28).

On Cloud Run, the runner asks the metadata server for an ID token whose audience is this service's URL, and sends
it as a bearer token. Google signs it. This checks the signature against Google's published keys, the issuer, the
audience, the expiry, and that its email is a verified service account that this deployment trusts as the runner.
This service lets anyone reach it (the app's users sign in with GitHub, not Google), so it checks the token itself
rather than leaving it to Cloud Run's invoker check.
"""

import jwt

from .errors import InvalidCredentials, Unavailable

GOOGLE_CERTS = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ("https://accounts.google.com", "accounts.google.com")


class GoogleIdentity:
    def __init__(self, audience, service_accounts, certs_url=GOOGLE_CERTS):
        self.audience = audience
        self.allowed = frozenset(account.lower() for account in service_accounts)
        self.keys = jwt.PyJWKClient(certs_url, cache_jwk_set=True, lifespan=3600, timeout=10)

    def verify(self, token):
        """The trusted service account the token proves, or InvalidCredentials."""
        if not self.audience or not self.allowed:
            raise InvalidCredentials("this deployment trusts no service identity")
        try:
            key = self.keys.get_signing_key_from_jwt(token)
        except jwt.PyJWKClientConnectionError as error:
            raise Unavailable(f"Google's keys cannot be fetched: {error}") from error
        except jwt.PyJWTError as error:
            raise InvalidCredentials(f"not a Google-signed token: {error}") from error
        try:
            claims = jwt.decode(token, key.key, algorithms=["RS256"], audience=self.audience, issuer=ISSUERS,
                                options={"require": ["exp", "iat", "aud", "iss"]})
        except jwt.PyJWTError as error:
            raise InvalidCredentials(f"the ID token is not valid here: {error}") from error
        email = claims.get("email")
        if not isinstance(email, str) or claims.get("email_verified") is not True or email.lower() not in self.allowed:
            raise InvalidCredentials("the ID token is not a service account trusted as the runner")
        return email
