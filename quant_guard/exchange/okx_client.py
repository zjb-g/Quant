"""quant_guard.exchange.okx_client: OKX 交易所客户端封装。

基于 ccxt，默认 public-only 模式（不读取密钥），仅访问公开行情。
私有接口（positions）需从环境变量读取 OKX_API_KEY/SECRET/PASSPHRASE。

安全说明：
- 严禁硬编码 API Key。
- public-only 模式下调用私有接口会抛 OKXClientError。
"""

import logging
import os
import time
from typing import List, Optional

import ccxt

from quant_guard.exchange.models import (
    FundingRate,
    MarkPrice,
    Ohlcv,
    Position,
    Side,
    Ticker,
)

logger = logging.getLogger(__name__)


class OKXClientError(Exception):
    """OKX 客户端异常基类。"""


class OKXClient:
    """OKX 交易所客户端（基于 ccxt.okx，永续合约 defaultType=swap）。

    参数：
        public_only: True 时仅访问公开行情，不读取密钥（默认）。
        timeout_ms: 请求超时（毫秒）。
        max_retries: 网络/限流类错误的最大重试次数。
    """

    def __init__(
        self,
        public_only: bool = True,
        timeout_ms: int = 10000,
        max_retries: int = 3,
    ) -> None:
        self.public_only = public_only
        self.timeout_ms = timeout_ms
        self.max_retries = max_retries

        params: dict = {
            "enableRateLimit": True,
            "timeout": timeout_ms,
            "options": {"defaultType": "swap"},
        }

        if not public_only:
            api_key = os.environ.get("OKX_API_KEY")
            api_secret = os.environ.get("OKX_API_SECRET")
            passphrase = os.environ.get("OKX_API_PASSPHRASE")
            if not all([api_key, api_secret, passphrase]):
                raise OKXClientError(
                    "private mode requires OKX_API_KEY / OKX_API_SECRET / "
                    "OKX_API_PASSPHRASE environment variables"
                )
            params["apiKey"] = api_key
            params["secret"] = api_secret
            params["password"] = passphrase

        self._exchange = ccxt.okx(params)

    # ------------------------------------------------------------------ #
    # 内部：带重试的调用
    # ------------------------------------------------------------------ #
    def _call(self, func, *args, **kwargs):
        """对网络/限流类错误指数退避重试，交易所逻辑错误直接抛出。"""
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except (
                ccxt.NetworkError,
                ccxt.RequestTimeout,
                ccxt.DDoSProtection,
            ) as exc:
                last_exc = exc
                wait = min(2**attempt, 10)
                logger.warning(
                    "attempt %d/%d failed: %s; retry in %ds",
                    attempt,
                    self.max_retries,
                    exc,
                    wait,
                )
                time.sleep(wait)
            except ccxt.AuthenticationError as exc:
                raise OKXClientError(f"authentication error: {exc}") from exc
            except ccxt.ExchangeError as exc:
                raise OKXClientError(f"exchange error: {exc}") from exc
        raise OKXClientError(f"max retries ({self.max_retries}) exceeded: {last_exc}")

    # ------------------------------------------------------------------ #
    # 公开行情接口
    # ------------------------------------------------------------------ #
    def get_ticker(self, symbol: str) -> Ticker:
        """获取最新行情快照。"""
        raw = self._call(self._exchange.fetch_ticker, symbol)
        return Ticker(
            symbol=symbol,
            last_price=float(raw["last"]),
            bid=float(raw["bid"]),
            ask=float(raw["ask"]),
            timestamp=int(raw["timestamp"]),
        )

    def get_ohlcv(
        self, symbol: str, timeframe: str = "15m", limit: int = 500
    ) -> List[Ohlcv]:
        """获取 K 线数据。"""
        raw = self._call(
            self._exchange.fetch_ohlcv, symbol, timeframe, limit=limit
        )
        return [
            Ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=int(c[0]),
                open=float(c[1]),
                high=float(c[2]),
                low=float(c[3]),
                close=float(c[4]),
                volume=float(c[5]),
            )
            for c in raw
        ]

    def get_funding_rate(self, symbol: str) -> FundingRate:
        """获取资金费率。"""
        raw = self._call(self._exchange.fetch_funding_rate, symbol)
        return FundingRate(
            symbol=symbol,
            funding_rate=float(raw["fundingRate"]),
            next_funding_time=int(raw.get("nextFundingTime", 0) or 0),
            timestamp=int(raw.get("timestamp", 0) or 0),
        )

    def get_mark_price(self, symbol: str) -> MarkPrice:
        """获取标记价格（从 fetch_ticker 提取 markPrice）。"""
        raw = self._call(self._exchange.fetch_ticker, symbol)
        mark = raw.get("markPrice") or raw.get("info", {}).get("markPx")
        if mark is None:
            raise OKXClientError(f"no mark price available for {symbol}")
        return MarkPrice(
            symbol=symbol,
            mark_price=float(mark),
            timestamp=int(raw["timestamp"]),
        )

    # ------------------------------------------------------------------ #
    # 私有接口
    # ------------------------------------------------------------------ #
    def get_positions(self, symbols: Optional[List[str]] = None) -> List[Position]:
        """获取账户持仓。public-only 模式下禁止调用。"""
        if self.public_only:
            raise OKXClientError(
                "get_positions requires private mode (public_only=False)"
            )
        raw = self._call(self._exchange.fetch_positions, symbols)
        positions: List[Position] = []
        for p in raw:
            side_str = p.get("side") or p.get("info", {}).get("posSide")
            if not side_str:
                continue
            positions.append(
                Position(
                    symbol=p["symbol"],
                    side=Side(side_str),
                    contracts=float(p.get("contracts", 0) or 0),
                    entry_price=float(p.get("entryPrice", 0) or 0),
                    mark_price=float(p.get("markPrice", 0) or 0),
                    leverage=float(p.get("leverage", 1) or 1),
                    unrealized_pnl=float(p.get("unrealizedPnl", 0) or 0),
                    liquidation_price=(
                        float(p["liquidationPrice"])
                        if p.get("liquidationPrice")
                        else None
                    ),
                    timestamp=int(p.get("timestamp", 0) or 0),
                )
            )
        return positions
