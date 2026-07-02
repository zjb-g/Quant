# 目录说明

轻量整理后的项目布局。`user_data/` 顶层结构遵循 Freqtrade 约定，不做大改。

## 根目录

| 路径 | 说明 |
|---|---|
| `quant_guard/` | 自研层：风控、执行、API、服务 |
| `user_data/` | Freqtrade 策略、配置、K 线、数据库 |
| `frontend/` | React + Vite 前端 |
| `scripts/` | 运维与数据脚本（见下表） |
| `tests/` | pytest |
| `docs/` | 文档与阶段记录 |
| `start.sh` | 根目录快捷入口 → `scripts/start.sh` |

## scripts/

| 子目录 | 内容 |
|---|---|
| `scripts/ops/` | 启停与状态：`start.sh`、`stop.sh`、`status.sh`、`start_web.sh` |
| `scripts/data/` | K 线下载、回测、dry-run：`download_*.sh/py`、`run_*.sh` |
| `scripts/backup/` | Cursor 本地备份与推送 |
| `scripts/`（根） | `precheck_dryrun.py`、`emergency_close_all.py`、`run_tests.sh` |

旧路径兼容：`scripts/start.sh` 等薄包装会转发到对应子目录，无需改习惯命令。

## 数据与数据库

| 路径 | 说明 |
|---|---|
| `user_data/data/` | K 线 feather 文件 |
| `user_data/db/users.sqlite` | Web 用户认证 |
| `user_data/db/tradesv3.dryrun.sqlite` | Freqtrade dry-run 成交库 |
| `user_data/logs/` | Freqtrade / Web 日志与 PID |

## 忽略项

- `cursor-backup/`：本地 Cursor 备份（`.gitignore`）
- `.env`：密钥，不入库
