"""Web UI 登录鉴权（JWT）。

支持：
- 环境变量单用户（管理员）
- SQLite 多用户注册登录
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Request
from pydantic import BaseModel, Field

PUBLIC_API_PATHS = frozenset(
    {
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/status",
    }
)


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    username: str
    user_id: Optional[int] = None


class AuthStatus(BaseModel):
    enabled: bool
    authenticated: bool = False
    allow_register: bool = False
    username: Optional[str] = None
    user_id: Optional[int] = None
    has_exchange_credentials: bool = False


@dataclass(frozen=True)
class TokenUser:
    username: str
    user_id: Optional[int] = None


def is_auth_enabled() -> bool:
    return os.environ.get("WEB_AUTH_ENABLED", "").lower() in ("1", "true", "yes")


def is_register_allowed() -> bool:
    if not is_auth_enabled():
        return False
    return os.environ.get("WEB_ALLOW_REGISTER", "true").lower() in ("1", "true", "yes")


def validate_auth_config() -> None:
    """启动时校验：启用鉴权则必须配置签名密钥。"""
    if not is_auth_enabled():
        return
    if not os.environ.get("WEB_AUTH_SECRET", "").strip():
        raise RuntimeError("WEB_AUTH_ENABLED=true 时必须设置 WEB_AUTH_SECRET（随机长字符串）")
    if not is_register_allowed():
        if not os.environ.get("WEB_AUTH_USERNAME", "").strip():
            raise RuntimeError("未开放注册时须设置 WEB_AUTH_USERNAME")
        if not os.environ.get("WEB_AUTH_PASSWORD", ""):
            raise RuntimeError("未开放注册时须设置 WEB_AUTH_PASSWORD")


def _auth_secret() -> str:
    secret = os.environ.get("WEB_AUTH_SECRET", "").strip()
    if secret:
        return secret
    return "dev-insecure-secret"


def _expected_env_credentials() -> tuple[str, str]:
    return (
        os.environ.get("WEB_AUTH_USERNAME", "").strip(),
        os.environ.get("WEB_AUTH_PASSWORD", ""),
    )


def create_access_token(username: str, user_id: Optional[int] = None) -> tuple[str, int]:
    hours = max(1, int(os.environ.get("WEB_AUTH_TOKEN_HOURS", "24")))
    expires_in = hours * 3600
    exp = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    payload: dict = {"sub": username, "exp": exp}
    if user_id is not None:
        payload["uid"] = user_id
    token = jwt.encode(payload, _auth_secret(), algorithm="HS256")
    return token, expires_in


def decode_token(token: str) -> Optional[TokenUser]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, _auth_secret(), algorithms=["HS256"])
        sub = payload.get("sub")
        if not isinstance(sub, str) or not sub:
            return None
        uid = payload.get("uid")
        user_id = int(uid) if uid is not None else None
        return TokenUser(username=sub, user_id=user_id)
    except (jwt.PyJWTError, TypeError, ValueError):
        return None


def verify_token(token: str) -> bool:
    return decode_token(token) is not None


def authenticate_env_user(username: str, password: str) -> bool:
    expected_user, expected_pass = _expected_env_credentials()
    if not expected_user or not expected_pass:
        return False
    user_ok = secrets.compare_digest(username, expected_user)
    pass_ok = secrets.compare_digest(password, expected_pass)
    return user_ok and pass_ok


def authenticate_user(username: str, password: str) -> Optional[TokenUser]:
    from quant_guard.services.user_store import authenticate_user as db_authenticate

    record = db_authenticate(username, password)
    if record:
        return TokenUser(username=record.username, user_id=record.id)
    if authenticate_env_user(username, password):
        return TokenUser(username=username, user_id=None)
    return None


def register_user(username: str, password: str) -> TokenUser:
    if not is_register_allowed():
        raise ValueError("当前未开放注册")
    from quant_guard.services.user_store import create_user

    record = create_user(username, password)
    return TokenUser(username=record.username, user_id=record.id)


def should_require_auth(path: str) -> bool:
    if not is_auth_enabled():
        return False
    if not path.startswith("/api/"):
        return False
    return path not in PUBLIC_API_PATHS


def extract_bearer_token(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def cors_allowed_origins() -> list[str]:
    raw = os.environ.get("WEB_ALLOWED_ORIGINS", "").strip()
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
