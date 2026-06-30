"""用户注册与凭证存储测试。"""

import os
from pathlib import Path

import pytest

from quant_guard.services import user_store


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "users.sqlite"
    monkeypatch.setattr(user_store, "DB_PATH", db_file)
    user_store.init_db()
    yield


def test_create_and_authenticate_user():
    user = user_store.create_user("trader01", "password123")
    assert user.username == "trader01"
    assert user_store.authenticate_user("trader01", "password123") is not None
    assert user_store.authenticate_user("trader01", "wrong") is None


def test_duplicate_username():
    user_store.create_user("alice", "password123")
    with pytest.raises(ValueError, match="已存在"):
        user_store.create_user("alice", "password456")


def test_save_and_load_credentials(monkeypatch):
    monkeypatch.setenv("WEB_AUTH_SECRET", "test-secret-for-encryption-key-32b")
    user = user_store.create_user("bob", "password123")
    user_store.save_credentials(
        user.id,
        user_store.UserCredentials(
            okx_api_key="key1",
            okx_api_secret="secret1",
            okx_passphrase="pass1",
        ),
    )
    creds = user_store.get_credentials(user.id)
    assert creds is not None
    assert creds.okx_api_key == "key1"
    assert creds.okx_complete


def test_merge_credentials_keeps_existing(monkeypatch):
    monkeypatch.setenv("WEB_AUTH_SECRET", "test-secret-for-encryption-key-32b")
    user = user_store.create_user("carol", "password123")
    user_store.save_credentials(
        user.id,
        user_store.UserCredentials(okx_api_key="k", okx_api_secret="s", okx_passphrase="p"),
    )
    merged = user_store.merge_credentials(
        user.id,
        user_store.UserCredentials(okx_api_key="new-key"),
    )
    assert merged.okx_api_key == "new-key"
    assert merged.okx_api_secret == "s"
