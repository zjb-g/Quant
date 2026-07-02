"""从 Binance 公开数据站 data.binance.vision 下载历史 K 线（OHLCV）。

数据源免费、无需 API Key。URL 使用大写无连字符符号（如 BTCUSDT）。
下载策略：所有周期优先用月线包（每月一个 zip，请求量少），当月用日线包补全。

用法：
    python scripts/download_binance_data.py --start 2025-06-26 --end 2026-06-26
    python scripts/download_binance_data.py --symbols BTCUSDT ETHUSDT --interval 15m --start 2025-06-26 --end 2026-06-26

输出：
    - CSV: user_data/data/binance/{SYMBOL}_{interval}_{start}_{end}.csv
    - Freqtrade feather: user_data/data/binance/{PAIR}-15m-futures.feather
      （PAIR 格式如 BTC/USDT:USDT，供 Freqtrade 回测直接使用）

注意：Binance 永续合约数据与 OKX 价格存在微小差异，回测结果仅供策略逻辑验证。
正式部署需用 OKX 数据（见 scripts/download_data.sh）。
"""

import argparse
import csv
import io
import os
import sys
import time
import zipfile
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Binance 符号 → Freqtrade pair 映射（未列出的自动推导：BTCUSDT → BTC/USDT:USDT）
SYMBOL_TO_PAIR = {
    "BTCUSDT": "BTC/USDT:USDT",
    "ETHUSDT": "ETH/USDT:USDT",
    "SOLUSDT": "SOL/USDT:USDT",
    "BNBUSDT": "BNB/USDT:USDT",
    "XRPUSDT": "XRP/USDT:USDT",
    "SUIUSDT": "SUI/USDT:USDT",
    "ZECUSDT": "ZEC/USDT:USDT",
    "DOGEUSDT": "DOGE/USDT:USDT",
    "ORDIUSDT": "ORDI/USDT:USDT",
    "FLOWUSDT": "FLOW/USDT:USDT",
    "ZENUSDT": "ZEN/USDT:USDT",
    "WLDUSDT": "WLD/USDT:USDT",
    "ONTUSDT": "ONT/USDT:USDT",
    "MAGICUSDT": "MAGIC/USDT:USDT",
    "FILUSDT": "FIL/USDT:USDT",
    "UNIUSDT": "UNI/USDT:USDT",
    "TRXUSDT": "TRX/USDT:USDT",
    "LPTUSDT": "LPT/USDT:USDT",
}

BASE = "https://data.binance.vision"
OUT_DIR = "user_data/data/binance"


def symbol_to_pair(symbol: str) -> str:
    """Binance 符号转 Freqtrade pair。"""
    if symbol in SYMBOL_TO_PAIR:
        return SYMBOL_TO_PAIR[symbol]
    if symbol.endswith("USDT"):
        base = symbol[:-4]
        return f"{base}/USDT:USDT"
    return symbol


def date_range(start_str: str, end_str: str):
    """生成日期字符串列表（YYYY-MM-DD）。"""
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")
    cur = start
    while cur <= end:
        yield cur.strftime("%Y-%m-%d")
        cur += timedelta(days=1)


def month_range(start_str: str, end_str: str):
    """生成月份字符串列表（YYYY-MM）。"""
    start = datetime.strptime(start_str[:7], "%Y-%m")
    end = datetime.strptime(end_str[:7], "%Y-%m")
    cur = start
    while cur <= end:
        yield cur.strftime("%Y-%m")
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)


def download_zip(url: str, retries: int = 3) -> bytes | None:
    """下载 zip，404 返回 None（无此日数据/当月月包未生成）。
    网络错误（URLError）重试，指数退避。"""
    for attempt in range(1, retries + 1):
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urlopen(req, timeout=30) as resp:
                return resp.read()
        except HTTPError as e:
            if e.code == 404:
                return None
            print(f"  HTTP {e.code}: {url}", file=sys.stderr)
            return None
        except URLError as e:
            if attempt < retries:
                wait = 2 ** attempt
                print(
                    f"  网络错误(重试 {attempt}/{retries}): {e}，{wait}s 后重试",
                    file=sys.stderr,
                )
                time.sleep(wait)
            else:
                print(f"  下载失败(已重试 {retries} 次): {url} - {e}", file=sys.stderr)
                return None
    return None


def extract_rows(zip_data: bytes | None) -> list[list[str]]:
    """从 zip 提取 CSV 行（保留前 6 列：open_time, o, h, l, c, v）。"""
    if zip_data is None:
        return []
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        names = zf.namelist()
        if not names:
            return []
        content = zf.read(names[0]).decode().strip()
        lines = content.split("\n")
        # 跳过表头行（open_time,...），仅保留数据行
        data_lines = [l for l in lines[1:] if l.strip()]
        return [l.strip().split(",") for l in data_lines]


def dedup_sort(rows: list[list[str]]) -> list[list[str]]:
    """按 open_time 去重并升序排列。"""
    seen: set[int] = set()
    deduped: list[list[str]] = []
    for row in rows:
        ts = int(row[0])
        if ts not in seen:
            seen.add(ts)
            deduped.append(row)
    deduped.sort(key=lambda r: int(r[0]))
    return deduped


def save_csv(filename: str, rows: list[list[str]]) -> str:
    """保存为 CSV（timestamp, datetime_utc, open, high, low, close, volume）。"""
    path = os.path.join(OUT_DIR, filename)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["timestamp", "datetime_utc", "open", "high", "low", "close", "volume"]
        )
        for row in rows:
            ts = int(row[0])
            dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            writer.writerow([ts, dt, row[1], row[2], row[3], row[4], row[5]])
    return path


def to_freqtrade_feather(
    symbol: str, interval: str, rows: list[list[str]]
) -> str | None:
    """转换为 Freqtrade feather 格式。需 pandas。"""
    try:
        import pandas as pd
    except ImportError:
        print("  [warn] pandas 未安装，跳过 feather 转换", file=sys.stderr)
        return None

    pair = symbol_to_pair(symbol)
    if pair == symbol and symbol not in SYMBOL_TO_PAIR:
        print(f"  [warn] 未知符号 {symbol}，跳过 feather", file=sys.stderr)
        return None

    # Freqtrade feather 文件名：BTC_USDT_USDT-15m-futures.feather
    ft_name = pair.replace("/", "_").replace(":", "_") + f"-{interval}-futures.feather"
    ft_path = os.path.join(OUT_DIR, ft_name)

    # Binance CSV 有 12 列，仅取前 6 列：open_time, o, h, l, c, v
    df = pd.DataFrame(
        [r[:6] for r in rows], columns=["ts", "open", "high", "low", "close", "volume"]
    )
    df["date"] = pd.to_datetime(df["ts"].astype(int), unit="ms", utc=True)
    df = df.drop(columns=["ts"])
    df = df.astype(
        {"open": float, "high": float, "low": float, "close": float, "volume": float}
    )
    df = df[["date", "open", "high", "low", "close", "volume"]]
    df.to_feather(ft_path)
    return ft_path


def download_symbol(
    symbol: str,
    interval: str,
    start: str,
    end: str,
    use_monthly: bool = False,
) -> list[list[str]]:
    """下载单个币种数据。

    策略：优先用月线包覆盖完整月份（请求量少，避免限流），
    当月用日线包逐日补全。use_monthly 参数已废弃，所有周期均优先月线包。
    """
    all_rows: list[list[str]] = []
    today_month = datetime.now(timezone.utc).strftime("%Y-%m")

    # 月线包覆盖完整月份（不含当月）
    months = list(month_range(start, end))
    for m in months:
        if m >= today_month:
            continue  # 当月月包可能未生成，交给日线包
        url = f"{BASE}/data/futures/um/monthly/klines/{symbol}/{interval}/{symbol}-{interval}-{m}.zip"
        z = download_zip(url)
        rows = extract_rows(z)
        all_rows.extend(rows)
        print(f"  月包 {m}: {len(rows)} 根", flush=True)
        time.sleep(0.15)

    # 当月用日线包补全
    month_start = f"{today_month}-01"
    if month_start <= end:
        print(f"  日线包补当月 {month_start} ~ {end}", flush=True)
        for d in date_range(month_start, end):
            url = f"{BASE}/data/futures/um/daily/klines/{symbol}/{interval}/{symbol}-{interval}-{d}.zip"
            z = download_zip(url)
            all_rows.extend(extract_rows(z))
            time.sleep(0.15)

    return dedup_sort(all_rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="从 Binance 公开数据站下载历史 K 线"
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=list(SYMBOL_TO_PAIR.keys()),
        help="币种列表（默认 BTC/ETH/SOL/BNB/XRP）",
    )
    parser.add_argument("--interval", default="15m", help="K 线周期（默认 15m）")
    parser.add_argument("--start", required=True, help="起始日期 YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="结束日期 YYYY-MM-DD")
    parser.add_argument(
        "--no-feather",
        action="store_true",
        help="不生成 Freqtrade feather（仅 CSV）",
    )
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)

    for symbol in args.symbols:
        print(f"[{symbol}] 下载 {args.interval} {args.start} ~ {args.end} ...", flush=True)

        rows = download_symbol(symbol, args.interval, args.start, args.end)

        if not rows:
            print(f"  [warn] {symbol} 无数据，跳过")
            continue

        # CSV
        csv_name = f"{symbol}_{args.interval}_{args.start.replace('-', '')}_{args.end.replace('-', '')}.csv"
        csv_path = save_csv(csv_name, rows)

        # 时间范围
        first_ts = int(rows[0][0])
        last_ts = int(rows[-1][0])
        first_dt = datetime.fromtimestamp(first_ts / 1000, tz=timezone.utc)
        last_dt = datetime.fromtimestamp(last_ts / 1000, tz=timezone.utc)

        print(f"  CSV: {csv_path} ({len(rows)} 根)")
        print(f"  范围: {first_dt} ~ {last_dt}")

        # Freqtrade feather
        if not args.no_feather:
            ft_path = to_freqtrade_feather(symbol, args.interval, rows)
            if ft_path:
                print(f"  Feather: {ft_path}")

    print("全部完成。")


if __name__ == "__main__":
    main()
