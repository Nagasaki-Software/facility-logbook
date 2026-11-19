@echo off
cd /d "%~dp0"
echo ==========================================
echo  統合アプリ サーバを起動しています...
echo  停止するにはこの画面を閉じるか Ctrl+C
echo ==========================================
echo.
if not exist ".venv\Scripts\python.exe" (
  echo .venv がありません。先に「初回セットアップ.bat」を実行してください。
  pause
  exit /b 1
)
".venv\Scripts\python.exe" run.py
pause
