# scripts 说明

脚本按用途分子目录；`scripts/*.sh` 保留薄包装，兼容旧命令。

## 运维 `ops/`

```bash
bash scripts/start.sh              # 或 bash start.sh
bash scripts/stop.sh
bash scripts/status.sh
bash scripts/start_web.sh          # 前台启动（调试用）
```

## 数据 `data/`

```bash
bash scripts/download_klines.sh all
bash scripts/download_data.sh      # Docker + Freqtrade 下载 OKX 数据
bash scripts/run_backtest.sh
bash scripts/run_dryrun.sh
```

## 备份 `backup/`

```bash
python3 scripts/backup/backup_cursor_local.py
python3 scripts/backup/push_cursor_backup.py
python3 scripts/backup/restore_cursor_local.py
```

## 根目录脚本

```bash
python3 scripts/precheck_dryrun.py
python3 scripts/emergency_close_all.py
bash scripts/run_tests.sh
```

详细目录见 [docs/DIRECTORY.md](../docs/DIRECTORY.md)。
