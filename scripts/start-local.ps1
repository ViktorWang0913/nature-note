#Requires -Version 7.3
param([ValidateSet('setup','api','web','admin','check')][string]$action='check')
$ErrorActionPreference='Stop'
$PSNativeCommandUseErrorActionPreference=$true

# 路径
$rootPath=Split-Path $PSScriptRoot -Parent
$pythonPath=Join-Path $rootPath '.venv/Scripts/python.exe'
$backendPath=Join-Path $rootPath 'backend'
$frontendPath=Join-Path $rootPath 'frontend'

# 主程序
Write-Output "[开始] 本地操作 $action"
switch ($action) {
 'setup' {
  Write-Output '[分支] 建立独立依赖环境'
  python -m venv (Join-Path $rootPath '.venv')
  & $pythonPath -m pip install -r (Join-Path $backendPath 'requirements.lock.txt')
  Set-Location -LiteralPath $frontendPath
  npm.cmd ci
  npm.cmd run build:admin
 }
 'api' {
  Write-Output '[分支] 启动独立 Web 后端'
  Set-Location -LiteralPath $backendPath
  New-Item -ItemType Directory -Path (Join-Path $backendPath 'data') -Force | Out-Null
  & $pythonPath -m alembic upgrade head
  & $pythonPath -m app.web_seed
  & $pythonPath -m uvicorn app.main:app --host 127.0.0.1 --port 8010
 }
 'web' {Write-Output '[分支] 启动网页'; Set-Location -LiteralPath $frontendPath; npm.cmd run dev}
 'admin' {Write-Output '[分支] 创建管理员'; Set-Location -LiteralPath $backendPath; & $pythonPath -m app.admin_setup}
 'check' {
  Write-Output '[分支] 检查和构建'
  Set-Location -LiteralPath $frontendPath
  npm.cmd run typecheck
  npm.cmd test
  npm.cmd run build
  Set-Location -LiteralPath $backendPath
  & $pythonPath -m pytest tests -q
 }
}
Write-Output "[结束] 本地操作 $action"
