#!/usr/bin/env bash
# 兼容旧用法，等价于 scripts/start.sh --foreground
exec "$(dirname "$0")/start.sh" --foreground "$@"
