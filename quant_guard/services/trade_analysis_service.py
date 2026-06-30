"""quant_guard.services.trade_analysis_service: 历史持仓统计分析与筛选。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def _parse_iso_ms(iso: str) -> int:
    if not iso:
        return 0
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _holding_hours(open_time: str, close_time: str) -> float:
    start = _parse_iso_ms(open_time)
    end = _parse_iso_ms(close_time)
    if not start or not end or end <= start:
        return 0.0
    return (end - start) / 3_600_000


def _bucket_stats(items: list[dict], key_fn) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for item in items:
        key = key_fn(item)
        groups.setdefault(key, []).append(item)

    result = []
    for label, rows in groups.items():
        wins = sum(1 for r in rows if float(r.get("pnl", 0)) >= 0)
        total = len(rows)
        result.append(
            {
                "label": label,
                "count": total,
                "wins": wins,
                "losses": total - wins,
                "win_rate": round(wins / total * 100, 2) if total else 0.0,
                "total_pnl": round(sum(float(r.get("pnl", 0)) for r in rows), 4),
                "avg_pnl": round(sum(float(r.get("pnl", 0)) for r in rows) / total, 4) if total else 0.0,
            }
        )
    return sorted(result, key=lambda x: x["count"], reverse=True)


def _leverage_bucket(leverage: float) -> str:
    lev = float(leverage or 1)
    if lev <= 3:
        return "1-3x"
    if lev <= 5:
        return "4-5x"
    if lev <= 10:
        return "6-10x"
    return "10x+"


def _holding_bucket(hours: float) -> str:
    if hours < 1:
        return "<1小时"
    if hours < 4:
        return "1-4小时"
    if hours < 24:
        return "4-24小时"
    if hours < 72:
        return "1-3天"
    if hours < 168:
        return "3-7天"
    return "7天+"


def filter_positions(
    positions: list[dict],
    *,
    symbol: Optional[str] = None,
    side: Optional[str] = None,
    close_type: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    position_ids: Optional[set[str]] = None,
    close_times: Optional[set[str]] = None,
    min_pnl: Optional[float] = None,
    max_pnl: Optional[float] = None,
) -> list[dict]:
    """按条件筛选持仓记录。"""
    from quant_guard.services.kline_service import _symbol_matches

    start_ms = _parse_iso_ms(start_time) if start_time else None
    end_ms = _parse_iso_ms(end_time) if end_time else None
    filtered: list[dict] = []

    for p in positions:
        if symbol and not _symbol_matches(str(p.get("symbol", "")), symbol):
            continue
        if close_times is not None and p.get("close_time") not in close_times:
            continue
        if side and p.get("side") != side:
            continue
        if close_type and p.get("close_type") != close_type:
            continue
        if position_ids is not None and p.get("position_id") not in position_ids:
            continue
        pnl = float(p.get("pnl", 0))
        if min_pnl is not None and pnl < min_pnl:
            continue
        if max_pnl is not None and pnl > max_pnl:
            continue

        open_ms = _parse_iso_ms(p.get("open_time", ""))
        close_ms = _parse_iso_ms(p.get("close_time", ""))
        if start_ms and close_ms and close_ms < start_ms:
            continue
        if end_ms and open_ms and open_ms > end_ms:
            continue
        filtered.append(p)
    return filtered


def sort_positions(
    positions: list[dict],
    sort_by: str = "close_time",
    order: str = "desc",
) -> list[dict]:
    """排序持仓记录。"""
    reverse = order.lower() != "asc"

    def sort_key(p: dict):
        if sort_by == "pnl":
            return float(p.get("pnl", 0))
        if sort_by == "pnl_ratio":
            return float(p.get("pnl_ratio", 0))
        if sort_by == "leverage":
            return float(p.get("leverage", 0))
        if sort_by == "open_time":
            return _parse_iso_ms(p.get("open_time", ""))
        return _parse_iso_ms(p.get("close_time", ""))

    return sorted(positions, key=sort_key, reverse=reverse)


def analyze_positions(positions: list[dict]) -> dict[str, Any]:
    """生成历史持仓统计分析。"""
    if not positions:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "total_pnl": 0.0,
            "avg_pnl": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "profit_factor": 0.0,
            "max_win": 0.0,
            "max_loss": 0.0,
            "total_fee": 0.0,
            "total_funding_fee": 0.0,
            "avg_holding_hours": 0.0,
            "by_side": [],
            "by_leverage": [],
            "by_holding": [],
            "by_close_type": [],
            "by_symbol": [],
        }

    wins = [p for p in positions if float(p.get("pnl", 0)) >= 0]
    losses = [p for p in positions if float(p.get("pnl", 0)) < 0]
    total = len(positions)
    gross_profit = sum(float(p.get("pnl", 0)) for p in wins)
    gross_loss = abs(sum(float(p.get("pnl", 0)) for p in losses))
    holding_hours = [_holding_hours(p.get("open_time", ""), p.get("close_time", "")) for p in positions]

    return {
        "total_trades": total,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / total * 100, 2),
        "total_pnl": round(sum(float(p.get("pnl", 0)) for p in positions), 4),
        "avg_pnl": round(sum(float(p.get("pnl", 0)) for p in positions) / total, 4),
        "avg_win": round(gross_profit / len(wins), 4) if wins else 0.0,
        "avg_loss": round(-gross_loss / len(losses), 4) if losses else 0.0,
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss > 0 else 0.0,
        "max_win": round(max((float(p.get("pnl", 0)) for p in positions), default=0.0), 4),
        "max_loss": round(min((float(p.get("pnl", 0)) for p in positions), default=0.0), 4),
        "total_fee": round(sum(float(p.get("fee", 0)) for p in positions), 4),
        "total_funding_fee": round(sum(float(p.get("funding_fee", 0)) for p in positions), 4),
        "avg_holding_hours": round(sum(holding_hours) / total, 2),
        "by_side": _bucket_stats(positions, lambda p: "做多" if p.get("side") == "long" else "做空"),
        "by_leverage": _bucket_stats(positions, lambda p: _leverage_bucket(p.get("leverage", 1))),
        "by_holding": _bucket_stats(
            positions,
            lambda p: _holding_bucket(_holding_hours(p.get("open_time", ""), p.get("close_time", ""))),
        ),
        "by_close_type": _bucket_stats(positions, lambda p: str(p.get("close_type", "unknown"))),
        "by_symbol": _bucket_stats(positions, lambda p: str(p.get("symbol", "unknown"))),
    }
