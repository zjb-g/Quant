"""tests/test_live_guard: live_guard 模块测试。"""

import pytest

from quant_guard.utils.live_guard import (
    LiveGuardResult,
    assert_live_guard,
    check_live_guard,
)


# ---------------------------------------------------------------------- #
# dry_run 模式总是通过
# ---------------------------------------------------------------------- #

def test_dry_run_always_passes():
    """dry_run=True 时总是通过，无需任何环境变量。"""
    result = check_live_guard(dry_run=True)
    assert result.passed is True
    assert result.missing == []


def test_dry_run_passes_with_empty_env():
    """dry_run=True 时即使无任何环境变量也通过。"""
    result = check_live_guard(dry_run=True)
    assert result.passed is True


def test_assert_dry_run_no_raise():
    """dry_run=True 时 assert 不抛异常。"""
    assert_live_guard(dry_run=True)


# ---------------------------------------------------------------------- #
# live 模式缺环境变量拒绝
# ---------------------------------------------------------------------- #

def test_live_rejects_without_env(monkeypatch):
    """live 模式缺所有环境变量时拒绝。"""
    # 清除所有相关环境变量
    for var in ["LIVE_TRADING_CONFIRMED", "RISK_CONFIG_LOADED",
                "TELEGRAM_ENABLED", "KILL_SWITCH_TESTED",
                "OKX_API_KEY", "OKX_API_SECRET", "OKX_API_PASSPHRASE"]:
        monkeypatch.delenv(var, raising=False)

    result = check_live_guard(dry_run=False)
    assert result.passed is False
    assert "LIVE_TRADING_CONFIRMED" in result.missing
    assert "OKX_API_KEY" in result.missing


def test_live_rejects_missing_one_var(monkeypatch):
    """live 模式缺一个环境变量时拒绝。"""
    env = {
        "LIVE_TRADING_CONFIRMED": "true",
        "RISK_CONFIG_LOADED": "true",
        "TELEGRAM_ENABLED": "true",
        "KILL_SWITCH_TESTED": "true",
        "OKX_API_KEY": "fake_key",
        "OKX_API_SECRET": "fake_secret",
        "OKX_API_PASSPHRASE": "fake_pass",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    # 删除一个
    monkeypatch.delenv("KILL_SWITCH_TESTED", raising=False)

    result = check_live_guard(dry_run=False)
    assert result.passed is False
    assert "KILL_SWITCH_TESTED" in result.missing


def test_live_passes_with_all_vars(monkeypatch):
    """live 模式所有环境变量满足时通过。"""
    env = {
        "LIVE_TRADING_CONFIRMED": "true",
        "RISK_CONFIG_LOADED": "true",
        "TELEGRAM_ENABLED": "true",
        "KILL_SWITCH_TESTED": "true",
        "OKX_API_KEY": "fake_key",
        "OKX_API_SECRET": "fake_secret",
        "OKX_API_PASSPHRASE": "fake_pass",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)

    result = check_live_guard(dry_run=False)
    assert result.passed is True
    assert result.missing == []


def test_live_rejects_false_values(monkeypatch):
    """live 模式环境变量为 false 时拒绝。"""
    monkeypatch.setenv("LIVE_TRADING_CONFIRMED", "false")
    monkeypatch.setenv("RISK_CONFIG_LOADED", "true")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("KILL_SWITCH_TESTED", "true")
    monkeypatch.setenv("OKX_API_KEY", "key")
    monkeypatch.setenv("OKX_API_SECRET", "secret")
    monkeypatch.setenv("OKX_API_PASSPHRASE", "pass")

    result = check_live_guard(dry_run=False)
    assert result.passed is False
    assert "LIVE_TRADING_CONFIRMED" in result.missing


def test_live_rejects_empty_okx_key(monkeypatch):
    """live 模式 OKX 密钥为空时拒绝。"""
    monkeypatch.setenv("LIVE_TRADING_CONFIRMED", "true")
    monkeypatch.setenv("RISK_CONFIG_LOADED", "true")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("KILL_SWITCH_TESTED", "true")
    monkeypatch.setenv("OKX_API_KEY", "")
    monkeypatch.setenv("OKX_API_SECRET", "secret")
    monkeypatch.setenv("OKX_API_PASSPHRASE", "pass")

    result = check_live_guard(dry_run=False)
    assert result.passed is False
    assert "OKX_API_KEY" in result.missing


# ---------------------------------------------------------------------- #
# assert_live_guard 抛异常
# ---------------------------------------------------------------------- #

def test_assert_live_rejects_raises(monkeypatch):
    """live 模式不满足时 assert 抛 PermissionError。"""
    for var in ["LIVE_TRADING_CONFIRMED", "RISK_CONFIG_LOADED",
                "TELEGRAM_ENABLED", "KILL_SWITCH_TESTED",
                "OKX_API_KEY", "OKX_API_SECRET", "OKX_API_PASSPHRASE"]:
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(PermissionError, match="live_guard"):
        assert_live_guard(dry_run=False)


def test_assert_live_passes_no_raise(monkeypatch):
    """live 模式全满足时 assert 不抛异常。"""
    env = {
        "LIVE_TRADING_CONFIRMED": "true",
        "RISK_CONFIG_LOADED": "true",
        "TELEGRAM_ENABLED": "true",
        "KILL_SWITCH_TESTED": "true",
        "OKX_API_KEY": "key",
        "OKX_API_SECRET": "secret",
        "OKX_API_PASSPHRASE": "pass",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)

    assert_live_guard(dry_run=False)  # 不抛异常


# ---------------------------------------------------------------------- #
# error_message
# ---------------------------------------------------------------------- #

def test_error_message_contains_missing():
    """error_message 包含缺失的环境变量名。"""
    result = LiveGuardResult(
        passed=False,
        missing=["LIVE_TRADING_CONFIRMED", "OKX_API_KEY"],
        failures=[],
    )
    msg = result.error_message
    assert "LIVE_TRADING_CONFIRMED" in msg
    assert "OKX_API_KEY" in msg


def test_error_message_empty_when_passed():
    """通过时 error_message 为空。"""
    result = LiveGuardResult(passed=True, missing=[], failures=[])
    assert result.error_message == ""
