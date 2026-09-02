from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from backend.api.auth import login, logout

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
def authenticate(request: LoginRequest):
    token = login(request.username, request.password)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    return {"access_token": token, "token_type": "bearer", "expires_in": 3600}


@router.post("/auth/logout")
def sign_out(authorization: str | None = Header(default=None)):
    if authorization and authorization.startswith("Bearer "):
        logout(authorization.removeprefix("Bearer "))
    return {"status": "logged_out"}