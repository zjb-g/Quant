"""tests/test_okx_client: OKXClient 单元测试（全 mock，不访问真实交易所）。"""

import inspect
from unittest.mock import MagicMock, patch

import ccxt
import pytest

from quant_guard.exchange.models import Ohlcv, Side, Ticker
from quant_guard.exchange.okx_client import OKXClient, OKXClientError


# ---------------------------------------------------------------------- #
# 实例化
# ---------------------------------------------------------------------- #
def test_public_only_init_creates_client_without_keys():
    """public-only 模式可实例化，不需要任何密钥。"""
    client = OKXClient(public_only=True)
    assert client.public_only is True
    assert client.max_retries == 3


@patch("quant_guard.exchange.okx_client.ccxt.okx")
def test_private_init_without_env_raises(mock_okx):
    """private 模式缺少环境变量时抛 OKXClientError。"""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(OKXClientError, match="environment variables"):
            OKXClient(public_only=False)


@patch("quant_guard.exchange.okx_client.ccxt.okx")
def test_private_init_with_env_succeeds(mock_okx):
    """private 模式提供完整环境变量后可实例化。"""
    env = {
        "OKX_API_KEY": "fake_key",
        "OKX_API_SECRET": "fake_secret",
        "OKX_API_PASSPHRASE": "fake_pass",
    }
    with patch.dict("os.environ", env, clear=False):
        client = OKXClient(public_only=False)
        assert client.public_only is False


# ---------------------------------------------------------------------- #
# 公开行情接口
# ---------------------------------------------------------------------- #
def _make_client_with_mock():
    """构造 OKXClient 并返回 (client, mock_exchange)。"""
    with patch("quant_guard.exchange.okx_client.ccxt.okx") as mock_okx:
        mock_exchange = MagicMock()
        mock_okx.return_value = mock_exchange
        client = OKXClient(public_only=True)
    return client, mock_exchange


def test_get_ticker():
    client, mock_ex = _make_client_with_mock()
    mock_ex.fetch_ticker.return_value = {
        "last": 50000.0,
        "bid": 49999.0,
        "ask": 50001.0,
        "timestamp": 1700000000000,
    }
    t = client.get_ticker("BTC/USDT:USDT")
    assert isinstance(t, Ticker)
    assert t.symbol == "BTC/USDT:USDT"
    assert t.last_price == 50000.0
    assert t.timestamp == 1700000000000
    mock_ex.fetch_ticker.assert_called_once_with("BTC/USDT:USDT")


def test_get_ohlcv():
    client, mock_ex = _make_client_with_mock()
    mock_ex.fetch_ohlcv.return_value = [
        [1700000000000, 49000.0, 50500.0, 48900.0, 50000.0, 100.0],
        [1700000900000, 50000.0, 51000.0, 49800.0, 50500.0, 120.0],
    ]
    candles = client.get_ohlcv("BTC/USDT:USDT", timeframe="15m", limit=2)
    assert len(candles) == 2
    assert all(isinstance(c, Ohlcv) for c in candles)
    assert candles[0].open == 49000.0
    assert candles[1].volume == 120.0
    mock_ex.fetch_ohlcv.assert_called_once_with(
        "BTC/USDT:USDT", "15m", limit=2
    )


def test_get_funding_rate():
    client, mock_ex = _make_client_with_mock()
    mock_ex.fetch_funding_rate.return_value = {
        "fundingRate": 0.0001,
        "nextFundingTime": 1700000800000,
        "timestamp": 1700000000000,
    }
    fr = client.get_funding_rate("BTC/USDT:USDT")
    assert fr.symbol == "BTC/USDT:USDT"
    assert fr.funding_rate == pytest.approx(0.0001)
    assert fr.next_funding_time == 1700000800000


def test_get_mark_price_from_mark_price_field():
    client, mock_ex = _make_client_with_mock()
    mock_ex.fetch_ticker.return_value = {
        "last": 50000.0,
        "bid": 49999.0,
        "ask": 50001.0,
        "timestamp": 1700000000000,
        "markPrice": 49995.0,
    }
    mp = client.get_mark_price("BTC/USDT:USDT")
    assert mp.mark_price == 49995.0


def test_get_mark_price_from_info_fallback():
    client, mock_ex = _make_client_with_mock()
    mock_ex.fetch_ticker.return_value = {
        "last": 50000.0,
        "bid": 49999.0,
        "ask": 50001.0,
        "timestamp": 1700000000000,
        "info": {"markPx": "49990.5"},
    }
    mp = client.get_mark_price("BTC/USDT:USDT")
    assert mp.mark_price == pytest.approx(49990.5)


def test_get_mark_price_unavailable_raises():
    client, mock_ex = _make_client_with_mock()
    mock_ex.fetch_ticker.return_value = {
        "last": 50000.0,
        "bid": 49999.0,
        "ask": 50001.0,
        "timestamp": 1700000000000,
        "info": {},
    }
    with pytest.raises(OKXClientError, match="no mark price"):
        client.get_mark_price("BTC/USDT:USDT")


# ---------------------------------------------------------------------- #
# 私有接口
# ---------------------------------------------------------------------- #
def test_get_positions_public_only_raises():
    client, _ = _make_client_with_mock()
    with pytest.raises(OKXClientError, match="private mode"):
        client.get_positions()


@patch("quant_guard.exchange.okx_client.ccxt.okx")
def test_get_positions_private(mock_okx):
    mock_exchange = MagicMock()
    mock_okx.return_value = mock_exchange
    mock_exchange.fetch_positions.return_value = [
        {
            "symbol": "BTC/USDT:USDT",
            "side": "long",
            "contracts": 0.1,
            "entryPrice": 49000.0,
            "markPrice": 50000.0,
            "leverage": 5,
            "unrealizedPnl": 100.0,
            "liquidationPrice": 42000.0,
            "timestamp": 1700000000000,
        }
    ]
    env = {
        "OKX_API_KEY": "k",
        "OKX_API_SECRET": "s",
        "OKX_API_PASSPHRASE": "p",
    }
    with patch.dict("os.environ", env, clear=False):
        client = OKXClient(public_only=False)
    positions = client.get_positions()
    assert len(positions) == 1
    assert positions[0].side == Side.LONG
    assert positions[0].leverage == 5.0
    assert positions[0].liquidation_price == 42000.0


# ---------------------------------------------------------------------- #
# 重试逻辑
# ---------------------------------------------------------------------- #
def test_retry_on_network_error_then_success():
    client, mock_ex = _make_client_with_mock()
    mock_ex.fetch_ticker.side_effect = [
        ccxt.NetworkError("net down"),
        {
            "last": 50000.0,
            "bid": 49999.0,
            "ask": 50001.0,
            "timestamp": 1700000000000,
        },
    ]
    with patch("quant_guard.exchange.okx_client.time.sleep") as mock_sleep:
        t = client.get_ticker("BTC/USDT:USDT")
    assert t.last_price == 50000.0
    assert mock_sleep.call_count == 1  # 重试前 sleep 一次


def test_retry_exhausted_raises():
    client, mock_ex = _make_client_with_mock()
    mock_ex.fetch_ticker.side_effect = ccxt.NetworkError("net down")
    with patch("quant_guard.exchange.okx_client.time.sleep"):
        with pytest.raises(OKXClientError, match="max retries"):
            client.get_ticker("BTC/USDT:USDT")


def test_exchange_error_not_retried():
    client, mock_ex = _make_client_with_mock()
    mock_ex.fetch_ticker.side_effect = ccxt.ExchangeError("bad symbol")
    with pytest.raises(OKXClientError, match="exchange error"):
        client.get_ticker("BAD/USDT:USDT")
    assert mock_ex.fetch_ticker.call_count == 1  # 不重试


# ---------------------------------------------------------------------- #
# 安全：无硬编码密钥
# ---------------------------------------------------------------------- #
def test_no_hardcoded_api_keys_in_source():
    """源码中不得出现硬编码的 API Key/Secret/Passphrase 字面量。"""
    src = inspect.getsource(OKXClient)
    # 允许出现环境变量名，但不允许出现疑似真实密钥字面量
    forbidden = ["apiKey=", '"sk-', '"api_key_"']
    for token in forbidden:
        assert token not in src, f"found suspicious token {token} in source"
