"""Tests for freqtrade_service."""

import os
from unittest.mock import MagicMock, patch

import pytest

from quant_guard.services.freqtrade_service import FreqtradeService, JobStatus


@pytest.fixture
def svc(tmp_path, monkeypatch):
    service = FreqtradeService()
    userdir = tmp_path / "user_data"
    data_dir = userdir / "data" / "binance"
    futures_dir = data_dir / "futures"
    data_dir.mkdir(parents=True)
    futures_dir.mkdir(parents=True)
    feather = data_dir / "BTC_USDT_USDT-15m-futures.feather"
    feather.write_bytes(b"")

    monkeypatch.setattr("quant_guard.services.freqtrade_service.USERDIR", userdir)
    monkeypatch.setattr(
        "quant_guard.services.freqtrade_service.BACKTEST_RESULTS_DIR",
        userdir / "backtest_results",
    )
    monkeypatch.setattr("quant_guard.services.freqtrade_service.LOG_DIR", userdir / "logs")
    monkeypatch.setattr(
        "quant_guard.services.freqtrade_service.PID_FILE",
        userdir / "logs" / "freqtrade.pid",
    )
    monkeypatch.setattr(
        "quant_guard.services.freqtrade_service.BACKTEST_CONFIG",
        tmp_path / "config.binance.json",
    )
    (tmp_path / "config.binance.json").write_text(
        '{"dry_run": true, "exchange": {"name": "binance"}}', encoding="utf-8"
    )
    return service


def test_ensure_futures_data_links(svc, tmp_path):
    data_dir = tmp_path / "user_data" / "data" / "binance"
    src = data_dir / "ETH_USDT_USDT-15m-futures.feather"
    src.write_bytes(b"x")
    count = svc.ensure_futures_data_links("binance")
    assert count >= 1
    dest = data_dir / "futures" / "ETH_USDT_USDT-15m-futures.feather"
    assert dest.is_symlink()


@patch("quant_guard.services.freqtrade_service.subprocess.run")
def test_run_backtest_sync_success(mock_run, svc, tmp_path):
    results_dir = tmp_path / "user_data" / "backtest_results"
    results_dir.mkdir(parents=True)
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    with patch.object(svc, "_latest_backtest_id", return_value="20260629-120000"):
        job = svc.run_backtest_sync("EmaCrossoverStrategy", "20250601-20250615")

    assert job.status == JobStatus.DONE
    assert job.result_id == "20260629-120000"
    mock_run.assert_called_once()


@patch("quant_guard.services.freqtrade_service.subprocess.run")
def test_run_backtest_sync_exit2_with_result(mock_run, svc):
    """exit 2 + 结果文件存在时视为成功（ccxt 退出噪音）。"""
    mock_run.return_value = MagicMock(returncode=2, stdout="", stderr="asyncio - ERROR - Unclosed connector")
    with patch.object(svc, "_latest_backtest_id", return_value="20260630-100000"):
        job = svc.run_backtest_sync("EmaCrossoverStrategy", "20250601-20250615")
    assert job.status == JobStatus.DONE
    assert job.result_id == "20260630-100000"


@patch("quant_guard.services.freqtrade_service.subprocess.run")
def test_run_backtest_sync_failure(mock_run, svc):
    mock_run.return_value = MagicMock(returncode=2, stdout="", stderr="No data")
    job = svc.run_backtest_sync("EmaCrossoverStrategy", "20250601-20250615")
    assert job.status == JobStatus.ERROR
    assert "回测失败" in (job.error or "")


def test_get_bot_state_default(svc):
    state = svc.get_bot_state()
    assert state.running is False
    assert state.dry_run is True


def test_get_bot_state_recovers_from_pid_file(svc, tmp_path, monkeypatch):
    log_dir = tmp_path / "user_data" / "logs"
    log_dir.mkdir(parents=True)
    monkeypatch.setattr("quant_guard.services.freqtrade_service.LOG_DIR", log_dir)
    monkeypatch.setattr("quant_guard.services.freqtrade_service.PID_FILE", log_dir / "freqtrade.pid")

    pid_file = log_dir / "freqtrade.pid"
    pid_file.write_text(str(os.getpid()), encoding="utf-8")

    with patch.object(svc, "_strategy_from_pid", return_value="FiftyTwoWeekHighApproachStrategy"):
        state = svc.get_bot_state()

    assert state.running is True
    assert state.pid == os.getpid()
    assert state.strategy == "FiftyTwoWeekHighApproachStrategy"
