"""quant_guard.services.kline_service: 本地 K 线数据加载与持仓复盘。

从 user_data/data/binance 或 okx 读取 feather/CSV，
结合历史持仓生成进出场标注数据。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

DATA_ROOT = Path("user_data/data")

# Freqtrade / 本地 K 线常用周期 → 毫秒
INTERVAL_MS: dict[str, int] = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "6h": 21_600_000,
    "12h": 43_200_000,
    "1d": 86_400_000,
    "1w": 604_800_000,
    "1M": 2_592_000_000,  # 30 天近似
}


def interval_to_ms(interval: str) -> int:
    """周期字符串转毫秒，未知周期按分钟数解析。"""
    if interval in INTERVAL_MS:
        return INTERVAL_MS[interval]
    m = re.match(r"^(\d+)([mhdwM])$", interval.strip())
    if not m:
        raise ValueError(f"不支持的 K 线周期: {interval}")
    n, unit = int(m.group(1)), m.group(2)
    mult = {"m": 60_000, "h": 3_600_000, "d": 86_400_000, "w": 604_800_000, "M": 2_592_000_000}
    return n * mult[unit]


def floor_to_interval(ts_ms: int, interval: str) -> int:
    """向下对齐到 K 线开盘时间（UTC）。"""
    step = interval_to_ms(interval)
    return (ts_ms // step) * step


def ceil_to_interval(ts_ms: int, interval: str) -> int:
    """向上对齐到 K 线开盘时间（UTC）。"""
    step = interval_to_ms(interval)
    return ((ts_ms + step - 1) // step) * step


def compute_chart_window_ms(
    positions: list,
    interval: str,
    *,
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
    padding_bars: int = 20,
) -> tuple[Optional[int], Optional[int]]:
    """根据持仓或时间范围计算 K 线加载窗口（含边界 padding）。"""
    step = interval_to_ms(interval)
    pad = step * padding_bars

    if start_ms is not None or end_ms is not None:
        win_start = floor_to_interval(start_ms, interval) if start_ms else None
        win_end = ceil_to_interval(end_ms, interval) if end_ms else None
        if win_start is not None:
            win_start = max(0, win_start - pad)
        if win_end is not None:
            win_end = win_end + pad
        return win_start, win_end

    times: list[int] = []
    for p in positions:
        for field in ("open_time", "close_time"):
            v = getattr(p, field, None)
            if v is None and isinstance(p, dict):
                v = p.get(field)
            if isinstance(v, str) and v:
                times.append(_parse_iso_ms(v))
            elif isinstance(v, (int, float)) and v:
                times.append(int(v))

    if not times:
        return None, None

    win_start = floor_to_interval(min(times), interval) - pad
    win_end = ceil_to_interval(max(times), interval) + pad
    return max(0, win_start), win_end


@dataclass
class Candle:
    time: int  # 毫秒时间戳
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class TradeMarker:
    position_id: str
    marker_type: str  # entry / exit
    time: int  # 毫秒
    price: float
    side: str
    pnl: float
    leverage: float
    close_type: str
    label: str


def normalize_inst(symbol: str) -> str:
    """统一为 OKX instId 格式：ETH-USDT-SWAP。"""
    s = symbol.strip()
    if s.endswith("-SWAP") or "-SWAP-OFF" in s:
        return s.split("-OFF")[0] if "-OFF" in s else s
    # ETH/USDT:USDT → ETH-USDT-SWAP
    if "/" in s:
        base = s.split("/")[0]
        return f"{base}-USDT-SWAP"
    if s.endswith("USDT") and "-" not in s:
        return f"{s.replace('USDT', '')}-USDT-SWAP"
    return s


def inst_to_base(symbol: str) -> str:
    """ETH-USDT-SWAP → ETH"""
    inst = normalize_inst(symbol)
    return inst.replace("-USDT-SWAP", "").split("-")[0]


def inst_to_feather_name(symbol: str, interval: str) -> str:
    base = inst_to_base(symbol)
    return f"{base}_USDT_USDT-{interval}-futures.feather"


def _symbol_matches(history_symbol: str, target_inst: str) -> bool:
    """历史持仓 symbol 可能与 instId / ccxt 格式不同。"""
    h = normalize_inst(history_symbol.strip())
    t = normalize_inst(target_inst)
    if h == t:
        return True
    if h.replace("/", "-").replace(":USDT", "") == t.replace("-SWAP", ""):
        return True
    h_base = inst_to_base(h) if "-SWAP" in h or "/" in h else h.split("-")[0]
    return h_base == inst_to_base(t)


def find_kline_file(symbol: str, interval: str) -> tuple[Optional[Path], str]:
    """查找 K 线文件，优先 binance，其次 okx。返回 (path, source)。"""
    fname = inst_to_feather_name(symbol, interval)
    for source in ("binance", "okx"):
        path = DATA_ROOT / source / fname
        if path.exists():
            return path, source

    # CSV 回退：{SYMBOL}USDT_{interval}_*.csv
    base = inst_to_base(symbol)
    binance_sym = f"{base}USDT"
    for source in ("binance", "okx"):
        pattern = f"{binance_sym}_{interval}_*.csv"
        if source == "okx":
            pattern = f"{base}-USDT_{interval}_*.csv"
        matches = sorted((DATA_ROOT / source).glob(pattern))
        if matches:
            return matches[-1], source
    return None, ""


def load_candles(
    symbol: str,
    interval: str,
    limit: int = 5000,
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
) -> tuple[List[Candle], str]:
    """加载 K 线，返回 (candles, data_source)。"""
    path, source = find_kline_file(symbol, interval)
    if path is None:
        raise FileNotFoundError(
            f"未找到 {normalize_inst(symbol)} {interval} K 线数据，请先运行 download_all_klines.sh"
        )

    if path.suffix == ".feather":
        import pandas as pd

        df = pd.read_feather(path)
        if "date" in df.columns:
            dates = pd.to_datetime(df["date"], utc=True)
            # feather 常见 datetime64[ms]；仅 ns 需除以 10**6 得到毫秒
            unit = getattr(dates.dtype, "unit", "ns")
            raw = dates.astype("int64")
            if unit == "ns":
                ts = raw // 10**6
            elif unit == "us":
                ts = raw // 10**3
            elif unit == "ms":
                ts = raw
            elif unit == "s":
                ts = raw * 1000
            else:
                ts = raw // 10**6
        else:
            ts = df["timestamp"].astype(int)
        rows = zip(
            ts,
            df["open"].astype(float),
            df["high"].astype(float),
            df["low"].astype(float),
            df["close"].astype(float),
            df["volume"].astype(float),
        )
    else:
        import csv

        rows = []
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append(
                    (
                        int(r["timestamp"]),
                        float(r["open"]),
                        float(r["high"]),
                        float(r["low"]),
                        float(r["close"]),
                        float(r["volume"]),
                    )
                )

    candles: List[Candle] = []
    for t, o, h, l, c, v in rows:
        if start_ms and t < start_ms:
            continue
        if end_ms and t > end_ms:
            continue
        candles.append(Candle(time=int(t), open=o, high=h, low=l, close=c, volume=v))

    candles.sort(key=lambda x: x.time)
    if limit > 0 and len(candles) > limit:
        candles = candles[-limit:]
    return candles, source


def _parse_iso_ms(iso: str) -> int:
    if not iso:
        return 0
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return int(dt.timestamp() * 1000)


def build_markers(positions: list, symbol: str) -> List[TradeMarker]:
    """从历史持仓构建进出场标注。positions 可为 PositionHistory 或 PositionHistory dataclass。"""
    markers: List[TradeMarker] = []
    for p in positions:
        sym = getattr(p, "symbol", None) or (p.get("symbol") if isinstance(p, dict) else "")
        if not _symbol_matches(sym, symbol):
            continue

        def _get(name: str):
            v = getattr(p, name, None)
            if v is not None:
                return v
            return p.get(name, "") if isinstance(p, dict) else ""

        pos_id = _get("position_id")
        side = _get("side")
        pnl = float(_get("pnl") or 0)
        lev = float(_get("leverage") or 1)
        close_type = _get("close_type")
        open_price = float(_get("open_avg_price") or 0)
        close_price = float(_get("close_avg_price") or 0)
        open_ms = _parse_iso_ms(_get("open_time"))
        close_ms = _parse_iso_ms(_get("close_time"))

        if open_ms and open_price:
            markers.append(
                TradeMarker(
                    position_id=pos_id,
                    marker_type="entry",
                    time=open_ms,
                    price=open_price,
                    side=side,
                    pnl=pnl,
                    leverage=lev,
                    close_type=close_type,
                    label=f"开{'多' if side == 'long' else '空'} {open_price:.2f} {lev}x",
                )
            )
        if close_ms and close_price:
            pnl_sign = "+" if pnl >= 0 else ""
            markers.append(
                TradeMarker(
                    position_id=pos_id,
                    marker_type="exit",
                    time=close_ms,
                    price=close_price,
                    side=side,
                    pnl=pnl,
                    leverage=lev,
                    close_type=close_type,
                    label=f"平 {close_price:.2f} {pnl_sign}{pnl:.2f}U",
                )
            )
    markers.sort(key=lambda m: m.time)
    return markers


def list_available_symbols() -> List[dict]:
    """扫描本地数据目录，返回可用币种列表。"""
    seen: dict[str, dict] = {}
    for source in ("binance", "okx"):
        dir_path = DATA_ROOT / source
        if not dir_path.exists():
            continue
        for f in dir_path.glob("*-*-futures.feather"):
            m = re.match(r"^(.+)_USDT_USDT-(.+)-futures\.feather$", f.name)
            if not m:
                continue
            base, interval = m.group(1), m.group(2)
            inst = f"{base}-USDT-SWAP"
            key = inst
            if key not in seen:
                seen[key] = {
                    "symbol": inst,
                    "base": base,
                    "source": source,
                    "intervals": [],
                }
            if interval not in seen[key]["intervals"]:
                seen[key]["intervals"].append(interval)
            if source == "binance":
                seen[key]["source"] = "binance"
    for item in seen.values():
        item["intervals"].sort(
            key=lambda x: ["1m", "5m", "15m", "1h", "4h", "12h", "1d"].index(x)
            if x in ["1m", "5m", "15m", "1h", "4h", "12h", "1d"]
            else 99
        )
    return sorted(seen.values(), key=lambda x: x["symbol"])
