#!/usr/bin/env python3
"""同步 cursor-backup/ 到 ~/cursor 仓库并 push 到 GitHub。"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STAGING = PROJECT_ROOT / "cursor-backup"
CURSOR_REPO = Path.home() / "cursor"
REMOTE = "git@github.com:zjb-g/cursor.git"


def run(cmd: list[str], cwd: Path) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> None:
    if not STAGING.exists():
        raise SystemExit("请先运行: python3 scripts/backup/backup_cursor_local.py")

    if not CURSOR_REPO.exists():
        run(["git", "clone", REMOTE, str(CURSOR_REPO)], cwd=CURSOR_REPO.parent)

    for item in STAGING.iterdir():
        dst = CURSOR_REPO / item.name
        if item.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(item, dst)
        else:
            shutil.copy2(item, dst)

    scripts_src = STAGING / "scripts"
    if scripts_src.exists():
        dst_scripts = CURSOR_REPO / "scripts"
        dst_scripts.mkdir(exist_ok=True)
        for f in scripts_src.iterdir():
            shutil.copy2(f, dst_scripts / f.name)

    run(["git", "add", "-A"], cwd=CURSOR_REPO)
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=CURSOR_REPO, capture_output=True, text=True
    )
    if not status.stdout.strip():
        print("无变更，跳过 commit")
        return

    run(
        ["git", "commit", "-m", "chore: 更新 Cursor 本机状态备份"],
        cwd=CURSOR_REPO,
    )
    run(["git", "push", "-u", "origin", "HEAD"], cwd=CURSOR_REPO)
    print(f"已推送到 {REMOTE}")


if __name__ == "__main__":
    main()
