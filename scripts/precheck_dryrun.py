"""scripts.precheck_dryrun: dry-run 启动前安全检查（T6.1）。

在启动 dry-run 前验证：
1. 没有 live 配置启用
2. API key 可为空或只读
3. 风控配置存在
4. dry_run 必须为 true

用法：
    python scripts/precheck_dryrun.py
    python scripts/precheck_dryrun.py --config user_data/config/config.dryrun.example.json
"""

import argparse
import json
import os
import sys
from pathlib import Path


def check_config_dry_run(config_path: str) -> list[str]:
    """检查配置文件 dry_run=true。"""
    errors = []
    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        return [f"配置文件读取失败: {e}"]

    if not config.get("dry_run", False):
        errors.append("dry_run 必须为 true（当前为 false 或缺失）")

    if config.get("trading_mode") != "futures":
        errors.append(f"trading_mode 应为 futures（当前: {config.get('trading_mode')}）")

    exchange = config.get("exchange", {})
    if exchange.get("key") and not os.environ.get("OKX_API_KEY"):
        errors.append("配置中含 API key 但非环境变量来源，可能泄露")

    return errors


def check_no_live_config() -> list[str]:
    """检查没有 live 配置被启用。"""
    errors = []
    live_env = os.environ.get("LIVE_TRADING_CONFIRMED", "false").lower()
    if live_env == "true":
        errors.append("LIVE_TRADING_CONFIRMED=true，dry-run 不应启用此变量")

    config_dir = Path("user_data/config")
    if config_dir.exists():
        for f in config_dir.glob("*.json"):
            if "live" in f.name and "example" not in f.name:
                try:
                    with open(f, encoding="utf-8") as fh:
                        c = json.load(fh)
                    if not c.get("dry_run", True):
                        errors.append(f"发现 live 配置 {f.name} 且 dry_run=false")
                except Exception:
                    pass
    return errors


def check_risk_config() -> list[str]:
    """检查风控配置存在。"""
    errors = []
    env_checks = [
        ("RISK_MAX_LEVERAGE", "5"),
        ("RISK_MAX_SINGLE_ORDER_NOTIONAL", "200"),
        ("RISK_MAX_TOTAL_NOTIONAL", "1000"),
    ]
    for key, default in env_checks:
        val = os.environ.get(key, default)
        try:
            float(val)
        except ValueError:
            errors.append(f"风控参数 {key} 无效: {val}")

    # 检查 RiskManager 可导入
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from quant_guard.risk.manager import RiskManager
        rm = RiskManager()
        if rm.config.max_leverage > 10:
            errors.append(f"杠杆上限过高: {rm.config.max_leverage}x")
    except Exception as e:
        errors.append(f"RiskManager 初始化失败: {e}")

    return errors


def check_data_exists() -> list[str]:
    """检查回测/dry-run 所需数据存在。"""
    errors = []
    data_dir = Path("user_data/data")
    if not data_dir.exists():
        errors.append("user_data/data 目录不存在，需先下载数据")
        return errors

    # 检查至少有一个交易所的数据目录
    exchange_dirs = [d for d in data_dir.iterdir() if d.is_dir()]
    if not exchange_dirs:
        errors.append("user_data/data 下无交易所数据目录")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="dry-run 启动前安全检查")
    parser.add_argument(
        "--config",
        default="user_data/config/config.dryrun.example.json",
        help="dry-run 配置文件路径",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  Dry-Run 启动前安全检查")
    print("=" * 60)
    print()

    all_errors = []
    all_warnings = []

    # 1. 配置检查
    print("[1/4] 检查 dry-run 配置...")
    errors = check_config_dry_run(args.config)
    if errors:
        all_errors.extend(errors)
        for e in errors:
            print(f"  [FAIL] {e}")
    else:
        print("  [OK] dry_run=true，配置有效")

    # 2. 无 live 配置
    print("[2/4] 检查无 live 配置启用...")
    errors = check_no_live_config()
    if errors:
        all_errors.extend(errors)
        for e in errors:
            print(f"  [FAIL] {e}")
    else:
        print("  [OK] 无 live 配置启用")

    # 3. 风控配置
    print("[3/4] 检查风控配置...")
    errors = check_risk_config()
    if errors:
        all_errors.extend(errors)
        for e in errors:
            print(f"  [FAIL] {e}")
    else:
        print("  [OK] 风控配置有效")

    # 4. 数据存在
    print("[4/4] 检查历史数据...")
    errors = check_data_exists()
    if errors:
        all_warnings.extend(errors)
        for e in errors:
            print(f"  [WARN] {e}")
    else:
        print("  [OK] 历史数据存在")

    print()
    print("=" * 60)
    if all_errors:
        print(f"  [FAIL] 检查未通过: {len(all_errors)} 个错误")
        for e in all_errors:
            print(f"     - {e}")
        print("  请修复以上错误后再启动 dry-run")
        sys.exit(1)
    else:
        print("  [OK] 所有检查通过，可以启动 dry-run")
        print()
        print("  启动命令:")
        print(f"    freqtrade trade --config {args.config} --strategy EmaCrossoverStrategy --userdir user_data")
        sys.exit(0)


if __name__ == "__main__":
    main()
