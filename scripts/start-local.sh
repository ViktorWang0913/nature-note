#!/usr/bin/env bash
set -euo pipefail

action=${1:-check}
rootPath=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
pythonPath="$rootPath/.venv/bin/python"
backendPath="$rootPath/backend"
frontendPath="$rootPath/frontend"

if (( $# > 1 )); then
  echo '用法：start-local.sh [setup|api|web|admin|check]' >&2
  exit 2
fi

echo "[开始] 本地操作 $action"
case "$action" in
  setup)
    echo '[分支] 建立独立依赖环境'
    python3 -m venv "$rootPath/.venv"
    "$pythonPath" -m pip install -r "$backendPath/requirements.lock.txt"
    cd -- "$frontendPath"
    npm ci
    npm run build:admin
    ;;
  api)
    echo '[分支] 启动独立 Web 后端'
    cd -- "$backendPath"
    mkdir -p data
    "$pythonPath" -m alembic upgrade head
    "$pythonPath" -m app.web_seed
    "$pythonPath" -m uvicorn app.main:app --host 127.0.0.1 --port 8010
    ;;
  web)
    echo '[分支] 启动网页'
    cd -- "$frontendPath"
    npm run dev
    ;;
  admin)
    echo '[分支] 创建管理员'
    cd -- "$backendPath"
    "$pythonPath" -m app.admin_setup
    ;;
  check)
    echo '[分支] 检查和构建'
    cd -- "$frontendPath"
    npm run typecheck
    npm test
    npm run build
    cd -- "$backendPath"
    "$pythonPath" -m pytest tests -q
    ;;
  *)
    echo '用法：start-local.sh [setup|api|web|admin|check]' >&2
    exit 2
    ;;
esac
echo "[结束] 本地操作 $action"
