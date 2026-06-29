"""scripts.emergency_close_all: 紧急全平脚本（T3.5）。

默认只打印平仓计划，不真实下单。
必须显式传入 --confirm-live 才允许真实执行。

用法：
    python scripts/emergency_close_all.py              # 仅打印计划
    python scripts/emergency_close_all.py --confirm-live # 真实执行
"""

import argparse
import os
import sys
from datetime import datetime, timezone

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="紧急全平 —— 平仓所有持仓"
    )
    parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="确认真实执行（默认仅打印计划，不下单）",
    )
    parser.add_argument(
        "--reason",
        default="manual_emergency_close",
        help="紧急全平原因",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  EMERGENCY CLOSE ALL")
    print("=" * 60)
    print(f"  时间: {datetime.now(timezone.utc).isoformat()}")
    print(f"  原因: {args.reason}")
    print(f"  确认实盘: {args.confirm_live}")
    print()

    if not args.confirm_live:
        print("  ⚠️  当前为安全模式（dry-run），仅打印计划，不真实下单。")
        print("  如需真实执行，请加 --confirm-live 参数。")
        print()
        print("  计划操作：")
        print("  1. 查询所有 open positions")
        print("  2. 对每个 position 发送 reduce-only market order")
        print("  3. 确认所有 positions 已平仓")
        print("  4. 激活 kill switch 防止重新开仓")
        print()
        print("  （需要 OKX_API_KEY 等环境变量配置才能查询真实持仓）")
        print("=" * 60)
        return

    # 真实执行前的安全检查
    live_confirmed = os.environ.get("LIVE_TRADING_CONFIRMED", "false").lower() == "true"
    if not live_confirmed:
        print("  ❌ 环境变量 LIVE_TRADING_CONFIRMED 未设为 true，拒绝执行。")
        print("  实盘操作需要同时满足：")
        print("  1. --confirm-live 命令行参数")
        print("  2. LIVE_TRADING_CONFIRMED=true 环境变量")
        print("=" * 60)
        sys.exit(1)

    print("  🚨 真实执行紧急全平...")
    print()

    # TODO: 接入真实 OKXClient 查询持仓并平仓
    # from quant_guard.exchange.okx_client import OKXClient
    # from quant_guard.risk.manager import RiskManager
    # client = OKXClient(public_only=False)
    # positions = client.get_positions()
    # for pos in positions:
    #     # 发送 reduce-only market order
    #     ...
    # rm = RiskManager()
    # rm.activate_kill_switch(args.reason)

    print("  ⚠️  真实执行逻辑待接入 OKXClient（需 T4.3 ExecutionEngine 完成）")
    print("=" * 60)


if __name__ == "__main__":
    main()
