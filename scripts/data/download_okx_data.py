"""从 OKX 公开行情 API 下载历史 K 线（ccxt，无需 API Key）。

用于 Binance 公开数据站不覆盖的 OKX 独有小币（LAB、BEAT、HYPE 等）。
输出格式与 download_binance_data.py 一致，存入 user_data/data/okx/。

用法：
    python scripts/download_okx_data.py --inst LAB-USDT-SWAP --interval 15m --start 2024-01-01
    python scripts/download_okx_data.py --insts LAB-USDT-SWAP BEAT-USDT-SWAP --intervals 15m 1h 1d
"""

import argparse
import csv
import os
import sys
import time
from datetime import datetime, timezone

import ccxt

OUT_DIR = "user_data/data/okx"

# OKX instId → ccxt symbol
def inst_to_symbol(inst: str) -> str:
  """LAB-USDT-SWAP → LAB/USDT:USDT；去掉 -OFF 后缀。"""
  base = inst.split("-OFF")[0]  # OL-USDT-SWAP-OFF20251029-2
  parts = base.replace("-SWAP", "").split("-")
  if len(parts) >= 2:
    return f"{parts[0]}/USDT:USDT"
  return inst


def inst_to_ft_name(inst: str, interval: str) -> str:
  sym = inst_to_symbol(inst)
  return sym.replace("/", "_").replace(":", "_") + f"-{interval}-futures.feather"


def parse_date(s: str) -> int:
  dt = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
  return int(dt.timestamp() * 1000)


def fetch_all_ohlcv(
  exchange: ccxt.Exchange,
  inst: str,
  symbol: str,
  interval: str,
  since_ms: int,
  until_ms: int | None = None,
) -> list[list]:
  """分页拉取全部 K 线（OKX history-candles，用 after 向历史翻页）。"""
  okx_bar = interval  # 1m/5m/15m/1H/4H/12H/1D 等
  bar_map = {"1h": "1H", "4h": "4H", "12h": "12H", "1d": "1D"}
  okx_bar = bar_map.get(interval, interval)

  all_rows: list[list] = []
  after: str | None = None
  max_pages = 500

  for _ in range(max_pages):
    params: dict = {"instId": inst.split("-OFF")[0], "bar": okx_bar, "limit": "300"}
    if after:
      params["after"] = after
    raw = exchange.public_get_market_history_candles(params)
    data = raw.get("data", [])
    if not data:
      break

    for c in data:
      ts = int(c[0])
      if ts < since_ms:
        continue
      if until_ms and ts > until_ms:
        continue
      row = [ts, float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])]
      all_rows.append(row)

    oldest_ts = int(data[-1][0])
    if oldest_ts < since_ms:
      break
    if len(data) < 300:
      break
    after = str(oldest_ts)
    time.sleep(0.15)

  seen: set[int] = set()
  deduped: list[list] = []
  for c in all_rows:
    if c[0] not in seen:
      seen.add(c[0])
      deduped.append(c)
  deduped.sort(key=lambda x: x[0])
  return deduped


def save_csv(path: str, rows: list[list]) -> None:
  with open(path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(
      ["timestamp", "datetime_utc", "open", "high", "low", "close", "volume"]
    )
    for c in rows:
      ts = int(c[0])
      dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S"
      )
      writer.writerow([ts, dt, c[1], c[2], c[3], c[4], c[5]])


def save_feather(path: str, rows: list[list]) -> None:
  import pandas as pd

  df = pd.DataFrame(
    rows, columns=["ts", "open", "high", "low", "close", "volume"]
  )
  df["date"] = pd.to_datetime(df["ts"].astype(int), unit="ms", utc=True)
  df = df.drop(columns=["ts"])
  df = df.astype(
    {"open": float, "high": float, "low": float, "close": float, "volume": float}
  )
  df = df[["date", "open", "high", "low", "close", "volume"]]
  df.to_feather(path)


def download_inst(
  exchange: ccxt.Exchange,
  inst: str,
  interval: str,
  start: str,
  end: str,
  no_feather: bool = False,
) -> int:
  symbol = inst_to_symbol(inst)
  since_ms = parse_date(start)
  until_ms = parse_date(end) + 86400 * 1000 - 1

  print(f"  [{inst}] {symbol} {interval} {start}~{end} ...", flush=True)
  try:
    rows = fetch_all_ohlcv(exchange, inst, symbol, interval, since_ms, until_ms)
  except Exception as e:
    print(f"  [FAIL] {inst} {interval}: {e}", file=sys.stderr)
    return 0

  if not rows:
    print(f"  [warn] {inst} {interval} 无数据")
    return 0

  tag = f"{inst.replace('-SWAP','')}_{interval}_{start.replace('-','')}_{end.replace('-','')}"
  csv_path = os.path.join(OUT_DIR, f"{tag}.csv")
  save_csv(csv_path, rows)

  if not no_feather:
    ft_path = os.path.join(OUT_DIR, inst_to_ft_name(inst, interval))
    save_feather(ft_path, rows)

  t0 = datetime.fromtimestamp(rows[0][0] / 1000, tz=timezone.utc)
  t1 = datetime.fromtimestamp(rows[-1][0] / 1000, tz=timezone.utc)
  print(f"  OK {len(rows)} 根 | {t0.date()} ~ {t1.date()} | CSV: {csv_path}")
  return len(rows)


def main() -> None:
  parser = argparse.ArgumentParser(description="从 OKX 下载历史 K 线（公开行情）")
  parser.add_argument("--inst", help="单个 instId，如 LAB-USDT-SWAP")
  parser.add_argument("--insts", nargs="+", help="多个 instId")
  parser.add_argument("--interval", default="15m")
  parser.add_argument("--intervals", nargs="+", help="多个周期")
  parser.add_argument("--start", required=True, help="YYYY-MM-DD")
  parser.add_argument("--end", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
  parser.add_argument("--no-feather", action="store_true")
  args = parser.parse_args()

  insts = args.insts or ([args.inst] if args.inst else [])
  if not insts:
    parser.error("请指定 --inst 或 --insts")

  intervals = args.intervals or [args.interval]
  os.makedirs(OUT_DIR, exist_ok=True)

  exchange = ccxt.okx(
    {"enableRateLimit": True, "timeout": 30000, "options": {"defaultType": "swap"}}
  )

  total = 0
  for inst in insts:
    print(f"\n[{inst}]", flush=True)
    for iv in intervals:
      total += download_inst(
        exchange, inst, iv, args.start, args.end, args.no_feather
      )

  print(f"\n全部完成，共 {total} 根 K 线。")


if __name__ == "__main__":
  main()
