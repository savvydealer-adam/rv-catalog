"""Google OAuth token verification for dashboard access."""

import os
from functools import lru_cache

from fastapi import Depends, HTTPException, Request

GOOGLE_CLIENT_ID = os.getenv(
    "GOOGLE_CLIENT_ID",
    "952362582307-ahfci2bl4ci37t8houtv1mngd0vplv21.apps.googleusercontent.com",
)
ALLOWED_DOMAIN = os.getenv("ALLOWED_DOMAIN", "savvydealer.com")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# In dev mode, skip auth
SKIP_AUTH = ENVIRONMENT == "development"


@lru_cache()
def _get_certs():
    """Fetch Google's public signing keys."""
    import httpx
    resp = httpx.get("https://www.googleapis.com/oauth2/v3/certs")
    resp.raise_for_status()
    return resp.json()


def verify_google_token(token: str) -> dict:
    """Verify a Google ID token and return the payload."""
    import jwt as pyjwt
    from jwt import PyJWKClient

    jwks_client = PyJWKClient("https://www.googleapis.com/oauth2/v3/certs")
    signing_key = jwks_client.get_signing_key_from_jwt(token)

    payload = pyjwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=GOOGLE_CLIENT_ID,
        issuer=["accounts.google.com", "https://accounts.google.com"],
    )

    email = payload.get("email", "")
    if not email.endswith(f"@{ALLOWED_DOMAIN}"):
        raise HTTPException(status_code=403, detail=f"Email domain not allowed: {email}")

    if not payload.get("email_verified", False):
        raise HTTPException(status_code=403, detail="Email not verified")

    return payload


def get_current_user(request: Request) -> dict | None:
    """Extract and verify the user from the Authorization header.

    In dev mode, returns a fake user. In prod, requires a valid Google ID token.
    """
    if SKIP_AUTH:
        return {"email": "dev@savvydealer.com", "name": "Dev User"}

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = auth_header.removeprefix("Bearer ")
    return verify_google_token(token)
