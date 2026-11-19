@echo off
cd /d "%~dp0"
echo ==========================================
echo  アプリ更新（このフォルダの最新プログラムを既存アプリへ上書き）
echo  ※ データ・設定・設備定義・config.json は変更しません
echo ==========================================
echo.
echo 【重要】更新したいPCのサーバ（起動.bat の黒い画面）を、先に停止してください。
echo.
echo 更新したい既存アプリのフォルダ（run.py がある facility-logbook フォルダ）を
echo この画面にドラッグ＆ドロップして Enter を押してください。
echo.
set /p DST="フォルダのパス: "
set DST=%DST:"=%

set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY if exist "%DST%\.venv\Scripts\python.exe" set "PY=%DST%\.venv\Scripts\python.exe"
if not defined PY set "PY=python"

"%PY%" "tools\update_app.py" "%DST%"
echo.
pause
