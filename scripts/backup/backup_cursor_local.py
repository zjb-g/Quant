#!/usr/bin/env python3
"""将本机 Cursor 项目状态原样备份到仓库 cursor-backup/（不做脱敏）。"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKUP_ROOT = PROJECT_ROOT / "cursor-backup"


def cursor_project_dir(project_root: Path) -> Path:
    slug = str(project_root.resolve()).lstrip("/").replace("/", "-")
    return Path.home() / ".cursor" / "projects" / slug


def _copy_tree(src: Path, dst: Path) -> int:
    if not src.exists():
        return 0
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
    cursor_project = cursor_project_dir(PROJECT_ROOT)
    cursor_home = Path.home() / ".cursor"
    skills_cursor = cursor_home / "skills-cursor"

    if not cursor_project.exists():
        raise SystemExit(f"未找到 Cursor 项目目录: {cursor_project}")

    if BACKUP_ROOT.exists():
        # 保留 README 与 scripts（推送用元数据）
        keep: dict[str, bytes] = {}
        for rel in ("README.md",):
            p = BACKUP_ROOT / rel
            if p.is_file():
                keep[rel] = p.read_bytes()
        scripts_keep: dict[str, bytes] = {}
        scripts_dir = BACKUP_ROOT / "scripts"
        if scripts_dir.is_dir():
            for f in scripts_dir.iterdir():
                if f.is_file():
                    scripts_keep[f.name] = f.read_bytes()
        shutil.rmtree(BACKUP_ROOT)
        BACKUP_ROOT.mkdir(parents=True)
        for rel, data in keep.items():
            (BACKUP_ROOT / rel).write_bytes(data)
        if scripts_keep:
            (BACKUP_ROOT / "scripts").mkdir(exist_ok=True)
            for name, data in scripts_keep.items():
                (BACKUP_ROOT / "scripts" / name).write_bytes(data)
    else:
        BACKUP_ROOT.mkdir(parents=True)

    stats: dict[str, int] = {}
    for name in (
        "agent-transcripts",
        "agent-tools",
        "assets",
        "canvases",
        "mcps",
        "terminals",
        "uploads",
    ):
        stats[name] = _copy_tree(cursor_project / name, BACKUP_ROOT / "project" / name)

    stats["skills-cursor"] = _copy_tree(skills_cursor, BACKUP_ROOT / "skills-cursor")

    for extra in ("ide_state.json",):
        src = cursor_home / extra
        if src.exists():
            shutil.copy2(src, BACKUP_ROOT / extra)
            stats[extra] = 1

    for extra_dir in ("rules", "skills", "commands", "plans"):
        src = cursor_home / extra_dir
        if src.exists():
            stats[extra_dir] = _copy_tree(src, BACKUP_ROOT / extra_dir)

    (BACKUP_ROOT / "PROJECT_PATH.txt").write_text(
        f"{PROJECT_ROOT.resolve()}\n", encoding="utf-8"
    )
    (BACKUP_ROOT / "CURSOR_PROJECT_SLUG.txt").write_text(
        f"{cursor_project.name}\n", encoding="utf-8"
    )

    meta = {
        "backed_up_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(PROJECT_ROOT.resolve()),
        "cursor_project_dir": str(cursor_project),
        "cursor_home": str(cursor_home),
        "files": stats,
        "mode": "verbatim",
    }
    (BACKUP_ROOT / "manifest.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    total = sum(stats.values()) + 2
    print(f"原样备份完成 → {BACKUP_ROOT}（{total} 个文件）")
    for key, n in stats.items():
        if n:
            print(f"  {key}: {n}")
    print(f"  项目路径: {PROJECT_ROOT.resolve()}")
    print(f"  Cursor 目录: {cursor_project}")

if __name__ == "__main__":
    main()
