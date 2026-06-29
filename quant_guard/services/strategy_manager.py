"""quant_guard.services.strategy_manager: 策略文件管理。

列出 / 保存 / 删除 / 验证策略文件。
"""

import ast
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

STRATEGIES_DIR = Path("user_data/strategies")


@dataclass
class StrategyInfo:
    """策略信息。"""

    filename: str
    name: str  # 类名
    description: str  # 从文件头注释提取
    size: int  # 文件大小（字节）
    has_errors: bool  # 语法检查是否失败
    error_msg: str  # 错误信息


def list_strategies() -> List[StrategyInfo]:
    """列出所有策略文件。"""
    if not STRATEGIES_DIR.exists():
        return []

    strategies = []
    for f in sorted(STRATEGIES_DIR.glob("*.py")):
        if f.name.startswith("_"):
            continue
        info = _parse_strategy_file(f)
        strategies.append(info)

    return strategies


def _parse_strategy_file(path: Path) -> StrategyInfo:
    """解析策略文件，提取类名和描述。"""
    content = path.read_text(encoding="utf-8")
    name = ""
    description = ""
    has_errors = False
    error_msg = ""

    # 语法检查
    try:
        tree = ast.parse(content)
        # 找 IStrategy 子类
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    base_name = ""
                    if isinstance(base, ast.Name):
                        base_name = base.id
                    elif isinstance(base, ast.Attribute):
                        base_name = base.attr
                    if "Strategy" in base_name:
                        name = node.name
                        break
    except SyntaxError as e:
        has_errors = True
        error_msg = str(e)

    # 提取文件头注释作为描述
    lines = content.split("\n")
    desc_lines = []
    for line in lines[:10]:
        if line.startswith("#") and not line.startswith("#!"):
            desc_lines.append(line.lstrip("# ").strip())
        elif line.strip() == "":
            continue
        elif not line.startswith("#"):
            break
    description = " ".join(desc_lines)[:200] if desc_lines else "无描述"

    if not name:
        # 从文件名推断
        name = path.stem

    return StrategyInfo(
        filename=path.name,
        name=name,
        description=description,
        size=path.stat().st_size,
        has_errors=has_errors,
        error_msg=error_msg,
    )


def save_strategy(filename: str, code: str) -> Path:
    """保存策略代码到文件。

    参数：
        filename: 文件名（如 MyStrategy.py）
        code: Python 代码

    返回：
        保存的文件路径

    异常：
        ValueError: 文件名无效或代码语法错误
    """
    # 文件名安全检查
    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*\.py$', filename):
        raise ValueError(f"无效的文件名: {filename}（需为合法 Python 文件名）")

    # 语法检查
    try:
        ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"代码语法错误: {e}") from e

    STRATEGIES_DIR.mkdir(parents=True, exist_ok=True)
    path = STRATEGIES_DIR / filename
    path.write_text(code, encoding="utf-8")
    return path


def delete_strategy(filename: str) -> bool:
    """删除策略文件。"""
    path = STRATEGIES_DIR / filename
    if not path.exists():
        return False
    path.unlink()
    return True


def get_strategy_code(filename: str) -> Optional[str]:
    """读取策略代码。"""
    path = STRATEGIES_DIR / filename
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")
