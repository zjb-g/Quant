"""scripts/walk_forward_backtest.py: 样本外与 walk-forward 验证脚本（T1.4）。

按时间窗口切分，训练集/测试集分离运行回测，
输出每个窗口的收益、最大回撤、交易次数。

用法：
    python scripts/walk_forward_backtest.py --strategy EmaCrossoverStrategy --train-months 3 --test-months 1
    python scripts/walk_forward_backtest.py --strategy FundingRateTrendStrategy --start 2025-06-01 --end 2026-06-01
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path


def generate_windows(start: str, end: str, train_days: int, test_days: int):
    """生成 walk-forward 窗口列表。

    参数：
        start: 起始日期 YYYY-MM-DD
        end: 结束日期 YYYY-MM-DD
        train_days: 训练集天数
        test_days: 测试集天数

    生成：
        [(train_start, train_end, test_start, test_end), ...]
    """
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    windows = []
    cur = start_dt
    while cur + timedelta(days=train_days + test_days) <= end_dt:
        train_start = cur
        train_end = cur + timedelta(days=train_days - 1)
        test_start = cur + timedelta(days=train_days)
        test_end = test_start + timedelta(days=test_days - 1)
        windows.append((
            train_start.strftime("%Y%m%d"),
            train_end.strftime("%Y%m%d"),
            test_start.strftime("%Y%m%d"),
            test_end.strftime("%Y%m%d"),
        ))
        cur = test_start  # 滑动窗口：下个窗口从当前测试集开始
    return windows


def run_backtest(strategy: str, timerange: str, config: str, userdir: str) -> dict:
    """运行一次回测，返回关键指标。"""
    r = subprocess.run(
        [
            sys.executable, "-m", "freqtrade", "backtesting",
            "--config", config,
            "--strategy", strategy,
            "--userdir", userdir,
            "--timerange", timerange,
            "--cache", "none",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    # 从 stdout 解析结果
    result = {
        "trades": 0,
        "profit_pct": 0,
        "drawdown_pct": 0,
        "win_rate": 0,
        "exit_code": r.returncode,
    }

    for line in r.stdout.split("\n"):
        if strategy in line and "|" in line and "Trades" not in line:
            # 解析策略摘要行
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 7:
                try:
                    result["trades"] = int(parts[2])
                    result["profit_pct"] = float(parts[4])
                    # drawdown 在第 7 列（含 USDT 和 %）
                    dd_str = parts[7].replace("USDT", "").replace("%", "").strip()
                    result["drawdown_pct"] = float(dd_str) if dd_str else 0
                    # win_rate 从 win/loss 格式解析
                    wl_parts = parts[6].split()
                    if len(wl_parts) >= 4:
                        wins = int(wl_parts[0])
                        total = int(wl_parts[0]) + int(wl_parts[2])
                        result["win_rate"] = (wins / total * 100) if total > 0 else 0
                except (ValueError, IndexError):
                    pass
            break

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-forward 回测验证")
    parser.add_argument("--strategy", default="EmaCrossoverStrategy", help="策略名")
    parser.add_argument("--config", default="user_data/config/config.gate.example.json", help="配置文件")
    parser.add_argument("--userdir", default="user_data", help="Freqtrade userdir")
    parser.add_argument("--start", default="20250601", help="起始日期 YYYYMMDD")
    parser.add_argument("--end", default="20260625", help="结束日期 YYYYMMDD")
    parser.add_argument("--train-days", type=int, default=90, help="训练集天数")
    parser.add_argument("--test-days", type=int, default=30, help="测试集天数")
    parser.add_argument("--output", default="docs/BACKTEST_VALIDATION.md", help="输出报告路径")
    args = parser.parse_args()

    # 日期格式转换
    start_str = f"{args.start[:4]}-{args.start[4:6]}-{args.start[6:8]}"
    end_str = f"{args.end[:4]}-{args.end[4:6]}-{args.end[6:8]}"

    windows = generate_windows(start_str, end_str, args.train_days, args.test_days)
    print(f"生成 {len(windows)} 个 walk-forward 窗口")
    print(f"策略: {args.strategy}")
    print(f"训练 {args.train_days} 天 + 测试 {args.test_days} 天")
    print()

    results = []
    for i, (tr_s, tr_e, te_s, te_e) in enumerate(windows, 1):
        print(f"--- 窗口 {i}/{len(windows)} ---")
        print(f"  训练: {tr_s} ~ {tr_e}")
        print(f"  测试: {te_s} ~ {te_e}")

        # 运行测试集回测
        timerange = f"{te_s}-{te_e}"
        print(f"  回测中...", end=" ", flush=True)
        result = run_backtest(args.strategy, timerange, args.config, args.userdir)
        print(f"trades={result['trades']} profit={result['profit_pct']:.2f}% dd={result['drawdown_pct']:.2f}%")

        results.append({
            "window": i,
            "train": f"{tr_s} ~ {tr_e}",
            "test": f"{te_s} ~ {te_e}",
            **result,
        })

    # 生成报告
    report_lines = [
        "# Walk-Forward Validation Report",
        "",
        f"**策略**: {args.strategy}",
        f"**时间范围**: {args.start} ~ {args.end}",
        f"**训练集**: {args.train_days} 天",
        f"**测试集**: {args.test_days} 天",
        f"**窗口数**: {len(windows)}",
        "",
        "---",
        "",
        "## 各窗口结果",
        "",
        "| 窗口 | 测试期 | 交易数 | 收益率% | 回撤% | 胜率% |",
        "|---|---|---|---|---|---|",
    ]

    total_profit = 0
    total_trades = 0
    profitable_windows = 0

    for r in results:
        report_lines.append(
            f"| {r['window']} | {r['test']} | {r['trades']} | "
            f"{r['profit_pct']:.2f} | {r['drawdown_pct']:.2f} | {r['win_rate']:.1f} |"
        )
        total_profit += r["profit_pct"]
        total_trades += r["trades"]
        if r["profit_pct"] > 0:
            profitable_windows += 1

    report_lines.extend([
        "",
        "## 汇总",
        "",
        f"- 总窗口数: {len(results)}",
        f"- 盈利窗口数: {profitable_windows}",
        f"- 平均收益率: {total_profit/len(results):.2f}%" if results else "",
        f"- 总交易数: {total_trades}",
        f"- 盈利窗口占比: {profitable_windows/len(results)*100:.1f}%" if results else "",
        "",
        "## 结论",
        "",
    ])

    if results:
        win_ratio = profitable_windows / len(results)
        if win_ratio >= 0.6:
            report_lines.append("✅ 多数窗口盈利，策略具备样本外稳健性。")
        elif win_ratio >= 0.4:
            report_lines.append("⚠️ 部分窗口盈利，策略稳健性一般，需进一步优化。")
        else:
            report_lines.append("❌ 多数窗口亏损，策略样本外表现不佳，需重新设计。")

    report_lines.append("")
    report_lines.append("---")

    report = "\n".join(report_lines)

    # 保存报告
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"\n报告已保存到 {args.output}")


if __name__ == "__main__":
    main()
