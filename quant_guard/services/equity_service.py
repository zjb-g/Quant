"""quant_guard.services.equity_service: 从 OKX 历史持仓推算权益曲线。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional


def _parse_iso_ms(iso: str) -> int:
    if not iso:
        return 0
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def compute_equity_curve(
    positions: list[dict],
    *,
    days: int = 30,
    base_equity: Optional[float] = None,
) -> list[dict]:
    """按平仓时间累计已实现盈亏，生成权益曲线与回撤。

    参数：
        positions: PositionHistory 字典列表（含 close_time、pnl、fee、funding_fee）
        days: 仅保留最近 N 天
        base_equity: 起始权益；默认用首笔前权益 = 当前累计 - 区间总盈亏
    """
    if not positions:
        return []

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    cutoff_ms = now_ms - days * 86_400_000

    rows = sorted(
        [p for p in positions if _parse_iso_ms(p.get("close_time", "")) >= cutoff_ms],
        key=lambda p: _parse_iso_ms(p.get("close_time", "")),
    )
    if not rows:
        return []

    net_pnls = [
        float(p.get("pnl", 0)) - float(p.get("fee", 0)) - float(p.get("funding_fee", 0))
        for p in rows
    ]
    total_pnl = sum(net_pnls)

    if base_equity is None:
        base_equity = max(100.0, 1000.0 - total_pnl)

    curve: list[dict] = []
    equity = base_equity
    peak = equity

    for row, delta in zip(rows, net_pnls):
        equity += delta
        if equity > peak:
            peak = equity
        dd = ((peak - equity) / peak * 100.0) if peak > 0 else 0.0
        curve.append({
            "timestamp": row.get("close_time", ""),
            "equity": round(equity, 4),
            "drawdown_pct": round(dd, 4),
        })

    return curve


def infer_base_equity_from_balance(free: float, used: float) -> float:
    """用当前账户余额估算权益基准。"""
    total = free + used
    return total if total > 0 else 1000.0
