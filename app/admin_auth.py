from __future__ import annotations

import hashlib
import hmac
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .settings import settings

security = HTTPBasic(auto_error=False)


def require_admin(credentials: HTTPBasicCredentials | None = Depends(security)) -> str:
    if not settings.admin_enabled:
        raise HTTPException(status_code=404, detail="Admin unavailable")
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )

    username_ok = secrets.compare_digest(credentials.username.encode("utf-8"), (settings.admin_username or "").encode("utf-8"))
    password_ok = secrets.compare_digest(credentials.password.encode("utf-8"), (settings.admin_password or "").encode("utf-8"))
    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def csrf_token(action: str, object_id: str = "") -> str:
    if not settings.app_secret_key:
        raise RuntimeError("APP_SECRET_KEY is not configured")
    message = f"{action}|{object_id}".encode()
    return hmac.new(settings.app_secret_key.encode(), message, hashlib.sha256).hexdigest()


def verify_csrf(token: str | None, action: str, object_id: str = "") -> None:
    if not token or not secrets.compare_digest(token.encode("utf-8"), csrf_token(action, object_id).encode("ascii")):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
