"""Freqtrade dry-run 模拟盘数据读取（SQLite trades 库）。"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DRYRUN_DB = PROJECT_ROOT / "tradesv3.dryrun.sqlite"
DEFAULT_WALLET = 1000.0


@dataclass
class DryRunTrade:
    id: int
    pair: str
    side: str
    amount: float
    open_rate: float
    mark_price: float
    leverage: float
    stake_amount: float
    unrealized_pnl: float
    open_date: str
    stop_loss: Optional[float]
    liquidation_price: Optional[float]
    strategy: str


@dataclass
class DryRunSummary:
    wallet_balance: float
    starting_balance: float
    open_trades: int
    closed_trades: int
    total_unrealized_pnl: float
    total_realized_pnl: float
    total_stake: float


def _db_path() -> Optional[Path]:
    if DRYRUN_DB.exists():
        return DRYRUN_DB
    alt = PROJECT_ROOT / "user_data" / "tradesv3.dryrun.sqlite"
    return alt if alt.exists() else None


def _fetch_mark_prices(pairs: list[str]) -> dict[str, float]:
    """用 OKX 公开行情估算标记价（失败则回退到开仓价）。"""
    if not pairs:
        return {}
    try:
        from quant_guard.exchange.okx_client import OKXClient

        client = OKXClient(public_only=True)
        prices: dict[str, float] = {}
        for pair in pairs:
            try:
                ticker = client.get_ticker(pair)
                prices[pair] = float(ticker.last_price)
            except Exception:
                continue
        return prices
    except Exception:
        return {}


def get_dryrun_summary(starting_balance: float = DEFAULT_WALLET) -> DryRunSummary:
    path = _db_path()
    if path is None:
        return DryRunSummary(
            wallet_balance=starting_balance,
            starting_balance=starting_balance,
            open_trades=0,
            closed_trades=0,
            total_unrealized_pnl=0.0,
            total_realized_pnl=0.0,
            total_stake=0.0,
        )

    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        open_rows = conn.execute(
            "SELECT pair, is_short, amount, open_rate, stake_amount, close_rate_requested, max_rate "
            "FROM trades WHERE is_open = 1"
        ).fetchall()
        closed_pnl = conn.execute(
            "SELECT COALESCE(SUM(close_profit_abs), 0) FROM trades WHERE is_open = 0"
        ).fetchone()[0]
        closed_count = conn.execute(
            "SELECT COUNT(*) FROM trades WHERE is_open = 0"
        ).fetchone()[0]

    pairs = list({r["pair"] for r in open_rows})
    marks = _fetch_mark_prices(pairs)

    unrealized = 0.0
    total_stake = 0.0
    for row in open_rows:
        open_rate = float(row["open_rate"] or 0)
        amount = float(row["amount"] or 0)
        stake = float(row["stake_amount"] or 0)
        is_short = bool(row["is_short"])
        mark = marks.get(row["pair"]) or float(row["close_rate_requested"] or row["max_rate"] or open_rate)
        if open_rate > 0 and amount > 0:
            if is_short:
                pnl = (open_rate - mark) / open_rate * stake
            else:
                pnl = (mark - open_rate) / open_rate * stake
        else:
            pnl = 0.0
        unrealized += pnl
        total_stake += stake

    realized = float(closed_pnl or 0)
    wallet = starting_balance + realized + unrealized

    return DryRunSummary(
        wallet_balance=wallet,
        starting_balance=starting_balance,
        open_trades=len(open_rows),
        closed_trades=int(closed_count or 0),
        total_unrealized_pnl=unrealized,
        total_realized_pnl=realized,
        total_stake=total_stake,
    )


def get_dryrun_open_trades() -> list[DryRunTrade]:
    path = _db_path()
    if path is None:
        return []

    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, pair, is_short, amount, open_rate, stake_amount, leverage,
                   open_date, stop_loss, liquidation_price, strategy,
                   close_rate_requested, max_rate, min_rate
            FROM trades WHERE is_open = 1
            ORDER BY open_date DESC
            """
        ).fetchall()

    pairs = list({r["pair"] for r in rows})
    marks = _fetch_mark_prices(pairs)
    trades: list[DryRunTrade] = []

    for row in rows:
        open_rate = float(row["open_rate"] or 0)
        amount = float(row["amount"] or 0)
        stake = float(row["stake_amount"] or 0)
        is_short = bool(row["is_short"])
        mark = marks.get(row["pair"]) or float(row["close_rate_requested"] or row["max_rate"] or open_rate)
        if open_rate > 0 and stake > 0:
            pnl = ((open_rate - mark) / open_rate * stake) if is_short else ((mark - open_rate) / open_rate * stake)
        else:
            pnl = 0.0

        trades.append(
            DryRunTrade(
                id=int(row["id"]),
                pair=row["pair"],
                side="short" if is_short else "long",
                amount=amount,
                open_rate=open_rate,
                mark_price=mark,
                leverage=float(row["leverage"] or 1),
                stake_amount=stake,
                unrealized_pnl=pnl,
                open_date=row["open_date"] or "",
                stop_loss=float(row["stop_loss"]) if row["stop_loss"] else None,
                liquidation_price=float(row["liquidation_price"]) if row["liquidation_price"] else None,
                strategy=row["strategy"] or "",
            )
        )
    return trades
