@echo off
cd /d "%~dp0"
if not exist "data\audit_log.csv" (
  echo まだ編集ログがありません（編集操作を行うと自動で作成されます）。
  pause
  exit /b 0
)
start "" "data\audit_log.csv"
