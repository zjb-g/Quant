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
    CloseType,
    FundingRate,
    MarkPrice,
    Ohlcv,
    Position,
    PositionHistory,
    Side,
    Ticker,
)

# OKX positions-history type → CloseType
_OKX_CLOSE_TYPE_MAP = {
    "1": CloseType.PARTIAL,
    "2": CloseType.FULL,
    "3": CloseType.LIQUIDATION,
    "4": CloseType.FORCED_REDUCTION,
    "5": CloseType.ADL,
}

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
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        passphrase: Optional[str] = None,
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
            resolved_key = api_key or os.environ.get("OKX_API_KEY")
            resolved_secret = api_secret or os.environ.get("OKX_API_SECRET")
            resolved_pass = passphrase or os.environ.get("OKX_API_PASSPHRASE")
            if not all([resolved_key, resolved_secret, resolved_pass]):
                raise OKXClientError(
                    "private mode requires OKX API credentials "
                    "(environment variables or constructor arguments)"
                )
            params["apiKey"] = resolved_key
            params["secret"] = resolved_secret
            params["password"] = resolved_pass

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

    @staticmethod
    def _parse_close_type(raw_type) -> CloseType:
        return _OKX_CLOSE_TYPE_MAP.get(str(raw_type or ""), CloseType.UNKNOWN)

    @staticmethod
    def _parse_position_history_item(item: dict) -> PositionHistory:
        """将 ccxt fetch_positions_history 或 OKX 原始记录解析为 PositionHistory。"""
        info = item.get("info") or item
        side_str = (
            item.get("side")
            or info.get("direction")
            or info.get("posSide")
            or "long"
        )
        symbol = item.get("symbol") or info.get("instId", "")
        if symbol and "/" not in symbol and info.get("instId"):
            # OKX instId → ccxt symbol 格式由上层展示，保留 instId 亦可
            symbol = info.get("instId", symbol)

        return PositionHistory(
            position_id=str(item.get("id") or info.get("posId") or ""),
            symbol=symbol,
            side=Side(side_str),
            leverage=float(item.get("leverage") or info.get("lever") or 1),
            margin_mode=str(item.get("marginMode") or info.get("mgnMode") or ""),
            open_avg_price=float(item.get("entryPrice") or info.get("openAvgPx") or 0),
            close_avg_price=float(item.get("lastPrice") or info.get("closeAvgPx") or 0),
            close_size=float(info.get("closeTotalPos") or 0),
            pnl=float(info.get("pnl") or item.get("realizedPnl") or 0),
            realized_pnl=float(item.get("realizedPnl") or info.get("realizedPnl") or 0),
            pnl_ratio=float(info.get("pnlRatio") or 0),
            fee=float(info.get("fee") or 0),
            funding_fee=float(info.get("fundingFee") or 0),
            close_type=OKXClient._parse_close_type(info.get("type")),
            open_time=int(item.get("timestamp") or info.get("cTime") or 0),
            close_time=int(item.get("lastUpdateTimestamp") or info.get("uTime") or 0),
        )

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
            contracts = float(p.get("contracts", 0) or 0)
            if contracts == 0:
                continue
            positions.append(
                Position(
                    symbol=p["symbol"],
                    side=Side(side_str),
                    contracts=contracts,
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

    def get_usdt_balance(self) -> dict:
        """获取 USDT 余额摘要。public-only 模式下禁止调用。"""
        if self.public_only:
            raise OKXClientError("get_usdt_balance requires private mode")
        raw = self._call(self._exchange.fetch_balance)
        usdt = raw.get("USDT", {}) or {}
        return {
            "total": float(usdt.get("total", 0) or 0),
            "free": float(usdt.get("free", 0) or 0),
            "used": float(usdt.get("used", 0) or 0),
        }

    def get_positions_history(
        self,
        symbols: Optional[List[str]] = None,
        limit: int = 100,
        inst_type: str = "SWAP",
        fetch_all: bool = False,
    ) -> List[PositionHistory]:
        """获取历史持仓（已平仓记录）。public-only 模式下禁止调用。

        参数：
            symbols: 可选，ccxt 格式交易对列表，如 ['BTC/USDT:USDT']
            limit: 返回条数上限；fetch_all=True 或 limit=0 时拉取全部（分页）
            inst_type: 产品类型，默认 SWAP（永续）
            fetch_all: True 时自动分页拉取全部历史
        """
        if self.public_only:
            raise OKXClientError(
                "get_positions_history requires private mode (public_only=False)"
            )

        if fetch_all or limit == 0:
            return self._fetch_positions_history_paginated(
                symbols=symbols, limit=0, inst_type=inst_type
            )

        page_limit = min(max(limit, 1), 100)

        # 超过 100 条时走分页
        if limit > 100:
            return self._fetch_positions_history_paginated(
                symbols=symbols, limit=limit, inst_type=inst_type
            )

        if hasattr(self._exchange, "fetch_positions_history"):
            kwargs: dict = {"limit": page_limit}
            if symbols:
                kwargs["symbols"] = symbols
            raw = self._call(self._exchange.fetch_positions_history, **kwargs)
            return [self._parse_position_history_item(item) for item in raw]

        params: dict = {"instType": inst_type, "limit": str(page_limit)}
        if symbols and len(symbols) == 1:
            sym = symbols[0].replace("/", "-").replace(":USDT", "-SWAP")
            params["instId"] = sym

        raw = self._call(self._exchange.private_get_account_positions_history, params)
        return [self._parse_position_history_item(item) for item in raw.get("data", [])]

    def _fetch_positions_history_paginated(
        self,
        symbols: Optional[List[str]] = None,
        limit: int = 0,
        inst_type: str = "SWAP",
        max_pages: int = 50,
    ) -> List[PositionHistory]:
        """分页拉取历史持仓。OKX 单次最多 100 条，用 after=uTime 翻页。"""
        results: List[PositionHistory] = []
        after: Optional[str] = None
        last_after: Optional[str] = None

        for _ in range(max_pages):
            params: dict = {"instType": inst_type, "limit": "100"}
            if after:
                params["after"] = after
            if symbols and len(symbols) == 1:
                sym = symbols[0].replace("/", "-").replace(":USDT", "-SWAP")
                params["instId"] = sym

            raw = self._call(
                self._exchange.private_get_account_positions_history, params
            )
            data = raw.get("data", [])
            if not data:
                break

            for item in data:
                results.append(self._parse_position_history_item(item))
                if limit > 0 and len(results) >= limit:
                    return results

            if len(data) < 100:
                break

            after = str(data[-1].get("uTime", ""))
            if not after or after == last_after:
                break
            last_after = after

        return results

    def create_reduce_only_market_order(
        self, symbol: str, position_side: Side, amount: float
    ) -> dict:
        """发送 reduce-only 市价平仓单。public-only 模式下禁止调用。"""
        if self.public_only:
            raise OKXClientError(
                "create_reduce_only_market_order requires private mode"
            )
        if amount <= 0:
            raise OKXClientError("close amount must be positive")
        order_side = "sell" if position_side == Side.LONG else "buy"
        return self._call(
            self._exchange.create_order,
            symbol,
            "market",
            order_side,
            amount,
            None,
            {"reduceOnly": True},
        )
