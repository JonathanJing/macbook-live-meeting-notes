#!/bin/zsh
set -euo pipefail

bundle_dir="${0:A:h}"
cd "$bundle_dir"

if ! command -v uv >/dev/null 2>&1; then
  print -u2 "未找到 uv。请先运行 'brew install uv'，然后重新执行 ./run.command"
  exit 1
fi

mkdir -p sessions

print "正在准备本地运行环境…"
print "首次运行可能需要下载模型，请保持网络连接。"
exec uv run --locked --extra notes --python 3.12 meeting-notes ui "$@"
