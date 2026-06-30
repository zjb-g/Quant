"""多用户账号与交易所凭证存储（SQLite + 加密）。"""

from __future__ import annotations

import base64
import hashlib
import os
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

DB_PATH = Path("user_data/db/users.sqlite")
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,32}$")


@dataclass(frozen=True)
class UserRecord:
    id: int
    username: str
    created_at: str


@dataclass(frozen=True)
class UserCredentials:
    okx_api_key: str = ""
    okx_api_secret: str = ""
    okx_passphrase: str = ""
    gate_api_key: str = ""
    gate_api_secret: str = ""

    @property
    def okx_complete(self) -> bool:
        return bool(self.okx_api_key and self.okx_api_secret and self.okx_passphrase)


def _fernet() -> Fernet:
    secret = os.environ.get("WEB_AUTH_SECRET", "").strip() or "dev-insecure-secret"
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def _encrypt(value: str) -> str:
    if not value:
        return ""
    return _fernet().encrypt(value.encode()).decode()


def _decrypt(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        return ""


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        _algo, salt, hash_hex = stored.split("$", 2)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000)
    return secrets.compare_digest(digest.hex(), hash_hex)


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_credentials (
                user_id INTEGER PRIMARY KEY,
                okx_api_key TEXT NOT NULL DEFAULT '',
                okx_api_secret TEXT NOT NULL DEFAULT '',
                okx_passphrase TEXT NOT NULL DEFAULT '',
                gate_api_key TEXT NOT NULL DEFAULT '',
                gate_api_secret TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )


def validate_username(username: str) -> None:
    if not _USERNAME_RE.match(username):
        raise ValueError("用户名需为 3-32 位字母、数字或下划线")


def validate_password(password: str) -> None:
    if len(password) < 8:
        raise ValueError("密码至少 8 位")


def create_user(username: str, password: str) -> UserRecord:
    validate_username(username)
    validate_password(password)
    init_db()
    created_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        try:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, _hash_password(password), created_at),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("用户名已存在") from exc
        user_id = int(cur.lastrowid)
    return UserRecord(id=user_id, username=username, created_at=created_at)


def authenticate_user(username: str, password: str) -> Optional[UserRecord]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, username, password_hash, created_at FROM users WHERE username = ? COLLATE NOCASE",
            (username,),
        ).fetchone()
    if not row:
        return None
    if not _verify_password(password, row[2]):
        return None
    return UserRecord(id=row[0], username=row[1], created_at=row[3])


def get_user_by_id(user_id: int) -> Optional[UserRecord]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, username, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return UserRecord(id=row[0], username=row[1], created_at=row[2])


def save_credentials(user_id: int, creds: UserCredentials) -> None:
    init_db()
    updated_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO user_credentials (
                user_id, okx_api_key, okx_api_secret, okx_passphrase,
                gate_api_key, gate_api_secret, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                okx_api_key = excluded.okx_api_key,
                okx_api_secret = excluded.okx_api_secret,
                okx_passphrase = excluded.okx_passphrase,
                gate_api_key = excluded.gate_api_key,
                gate_api_secret = excluded.gate_api_secret,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                _encrypt(creds.okx_api_key),
                _encrypt(creds.okx_api_secret),
                _encrypt(creds.okx_passphrase),
                _encrypt(creds.gate_api_key),
                _encrypt(creds.gate_api_secret),
                updated_at,
            ),
        )


def get_credentials(user_id: int) -> Optional[UserCredentials]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            """
            SELECT okx_api_key, okx_api_secret, okx_passphrase, gate_api_key, gate_api_secret
            FROM user_credentials WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    if not row:
        return None
    creds = UserCredentials(
        okx_api_key=_decrypt(row[0]),
        okx_api_secret=_decrypt(row[1]),
        okx_passphrase=_decrypt(row[2]),
        gate_api_key=_decrypt(row[3]),
        gate_api_secret=_decrypt(row[4]),
    )
    if not any((creds.okx_api_key, creds.okx_api_secret, creds.okx_passphrase, creds.gate_api_key, creds.gate_api_secret)):
        return None
    return creds


def merge_credentials(user_id: int, patch: UserCredentials) -> UserCredentials:
    """合并更新：空字段保留原值。"""
    current = get_credentials(user_id) or UserCredentials()
    merged = UserCredentials(
        okx_api_key=patch.okx_api_key or current.okx_api_key,
        okx_api_secret=patch.okx_api_secret or current.okx_api_secret,
        okx_passphrase=patch.okx_passphrase or current.okx_passphrase,
        gate_api_key=patch.gate_api_key or current.gate_api_key,
        gate_api_secret=patch.gate_api_secret or current.gate_api_secret,
    )
    save_credentials(user_id, merged)
    return merged
