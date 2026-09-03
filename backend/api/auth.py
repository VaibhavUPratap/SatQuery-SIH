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


def logout(token: str) -> None:
    _tokens.pop(token, None)


def current_user(authorization: str | None = Header(default=None)) -> str:
    if not settings.SATQUERY_AUTH_REQUIRED:
        return "prototype"
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    token = authorization.removeprefix("Bearer ")
    record = _tokens.get(token)
    if not record or record[1] <= time.time():
        _tokens.pop(token, None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session.")
    return record[0]