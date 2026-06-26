"""紧急全平脚本占位。

TODO T3.5: 实现 emergency_close_all。
- 默认只打印平仓计划，不真实下单。
- 必须显式传入 --confirm-live 才允许真实执行。
"""
import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="紧急全平（占位）")
    parser.add_argument("--confirm-live", action="store_true", help="确认真实执行（默认不执行）")
    args = parser.parse_args()
    print("[placeholder] emergency_close_all - 待 T3.5 实现")
    print(f"confirm_live={args.confirm_live}")


if __name__ == "__main__":
    main()
