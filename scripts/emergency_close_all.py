"""scripts.emergency_close_all: 紧急全平脚本。

默认 dry-run（模拟）；真实平仓需 LIVE_TRADING_CONFIRMED=true。

用法：
    python scripts/emergency_close_all.py
    python scripts/emergency_close_all.py --confirm-live
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> None:
    parser = argparse.ArgumentParser(description="紧急全平 —— 平仓所有持仓")
    parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="确认真实执行（还需 LIVE_TRADING_CONFIRMED=true）",
    )
    parser.add_argument("--reason", default="manual_emergency_close")
    args = parser.parse_args()

    if args.confirm_live:
        os.environ["LIVE_TRADING_CONFIRMED"] = "true"

    from quant_guard.services.control_service import control_service

    result = control_service.emergency_close_all(reason=args.reason)
    print(result)
    if result.get("status") == "emergency_close_skipped":
        sys.exit(1)


if __name__ == "__main__":
    main()
