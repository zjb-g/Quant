#!/usr/bin/env python3
"""从仓库 cursor-backup/ 原样还原 Cursor 本机状态（换机 / 重装后使用）。"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKUP_ROOT = PROJECT_ROOT / "cursor-backup"


def cursor_project_dir(project_root: Path) -> Path:
    slug = str(project_root.resolve()).lstrip("/").replace("/", "-")
    return Path.home() / ".cursor" / "projects" / slug


def _restore_tree(src: Path, dst: Path) -> int:
    if not src.exists():
        return 0
    dst.mkdir(parents=True, exist_ok=True)
    count = 0
    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(src)
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, out)
        count += 1
    return count


def main() -> None:
    if not BACKUP_ROOT.exists():
        raise SystemExit(f"未找到备份目录: {BACKUP_ROOT}，请先 git pull 或运行 backup 脚本")

    cursor_home = Path.home() / ".cursor"
    cursor_project = cursor_project_dir(PROJECT_ROOT)

    saved_slug = (BACKUP_ROOT / "CURSOR_PROJECT_SLUG.txt").read_text(encoding="utf-8").strip()
    if saved_slug and saved_slug != cursor_project.name:
        print(
            f"警告: 备份时的 Cursor 项目目录为 {saved_slug}，\n"
            f"      当前路径推算为 {cursor_project.name}。\n"
            f"      请确保项目 clone 在相同绝对路径，否则历史对话可能无法关联。",
            file=sys.stderr,
        )

    stats: dict[str, int] = {}
    project_backup = BACKUP_ROOT / "project"
    for name in (
        "agent-transcripts",
        "agent-tools",
        "assets",
        "canvases",
        "mcps",
        "terminals",
        "uploads",
    ):
        stats[name] = _restore_tree(project_backup / name, cursor_project / name)

    stats["skills-cursor"] = _restore_tree(
        BACKUP_ROOT / "skills-cursor", cursor_home / "skills-cursor"
    )

    for extra in ("ide_state.json",):
        src = BACKUP_ROOT / extra
        if src.exists():
            shutil.copy2(src, cursor_home / extra)
            stats[extra] = 1

    for extra_dir in ("rules", "skills", "commands", "plans"):
        stats[extra_dir] = _restore_tree(BACKUP_ROOT / extra_dir, cursor_home / extra_dir)

    print(f"还原完成 → {cursor_project}")
    for key, n in stats.items():
        if n:
            print(f"  {key}: {n}")
    print("\n下一步: 用 Cursor SSH Remote 打开本项目目录，历史 Agent 对话应出现在侧边栏。")


if __name__ == "__main__":
    main()
