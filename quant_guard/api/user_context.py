"""请求级当前用户上下文。"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException

from quant_guard.api.auth import is_auth_enabled
from quant_guard.exchange.okx_client import OKXClient, OKXClientError
from quant_guard.services.exchange_service import ExchangeService
from quant_guard.services.user_store import UserCredentials, get_credentials

current_user_id: ContextVar[Optional[int]] = ContextVar("current_user_id", default=None)
current_username: ContextVar[Optional[str]] = ContextVar("current_username", default=None)


@dataclass(frozen=True)
class CurrentUser:
    username: str
    user_id: Optional[int] = None


def set_current_user(username: str, user_id: Optional[int]) -> tuple:
    t1 = current_username.set(username)
    t2 = current_user_id.set(user_id)
    return t1, t2


def reset_current_user(tokens: tuple) -> None:
    current_username.reset(tokens[0])
    current_user_id.reset(tokens[1])


def get_current_user() -> Optional[CurrentUser]:
    username = current_username.get()
    if not username:
        return None
    return CurrentUser(username=username, user_id=current_user_id.get())


def get_current_user_credentials() -> Optional[UserCredentials]:
    user_id = current_user_id.get()
    if user_id is None:
        return None
    return get_credentials(user_id)


def require_registered_user() -> CurrentUser:
    user = get_current_user()
    if user is None:
        raise HTTPException(status_code=401, detail="未登录")
    if user.user_id is None:
        raise HTTPException(status_code=400, detail="管理员账号请在「交易所连接」使用环境变量密钥，或注册独立账号")
    return user


def credentials_configured() -> bool:
    if not is_auth_enabled():
        return True
    user_id = current_user_id.get()
    if user_id is None:
        return True
    creds = get_credentials(user_id)
    return bool(creds and creds.okx_complete)


def get_okx_client() -> OKXClient:
    """按当前登录用户或环境变量构建 OKX 客户端。"""
    user_id = current_user_id.get()
    if user_id is not None:
        creds = get_credentials(user_id)
        if not creds or not creds.okx_complete:
            raise HTTPException(
                status_code=400,
                detail="请先在「交易所连接」页面保存您的 OKX API Key",
            )
        try:
            return OKXClient(
                public_only=False,
                api_key=creds.okx_api_key,
                api_secret=creds.okx_api_secret,
                passphrase=creds.okx_passphrase,
            )
        except OKXClientError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        return OKXClient(public_only=False)
    except OKXClientError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def get_exchange_service() -> ExchangeService:
    user_id = current_user_id.get()
    if user_id is not None:
        creds = get_credentials(user_id)
        return ExchangeService(credentials=creds or UserCredentials())
    return ExchangeService()

