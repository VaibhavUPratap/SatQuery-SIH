"""Small prototype token layer for local/demo deployments."""
import hmac
import secrets
import time
from typing import Dict

from fastapi import Header, HTTPException, status
from backend.config import settings

_tokens: Dict[str, tuple[str, float]] = {}


def login(username: str, password: str) -> str | None:
    expected_user = settings.SATQUERY_DEMO_USERNAME
    expected_password = settings.SATQUERY_DEMO_PASSWORD
    if not hmac.compare_digest(username, expected_user) or not hmac.compare_digest(password, expected_password):
        return None
    token = secrets.token_urlsafe(32)
    _tokens[token] = (username, time.time() + 3600)
    return token


def create_access_token(data: dict) -> str:
    """Create a local prototype token for tests and programmatic clients."""
    username = str(data.get("sub") or "")
    if not username:
        raise ValueError("Token subject is required.")
    token = secrets.token_urlsafe(32)
    _tokens[token] = (username, time.time() + 3600)
    return token


def logout(token: str) -> None:
    _tokens.pop(token, None)


def current_user(authorization: str | None = Header(default=None)) -> str:
    if not authorization:
        if not settings.SATQUERY_AUTH_REQUIRED:
            return "prototype"
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    token = authorization.removeprefix("Bearer ")
    record = _tokens.get(token)
    if record and record[1] > time.time():
        return record[0]
    _tokens.pop(token, None)
    if not settings.SATQUERY_AUTH_REQUIRED:
        return "prototype"
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session.")