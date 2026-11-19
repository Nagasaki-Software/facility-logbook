@echo off
cd /d "%~dp0"
echo ==========================================
echo  他PC・単体アプリのデータ取り込み
echo  （運転記録／点検を自動判定して取り込みます）
echo ==========================================
echo.
echo 【重要】取り込み前に、統合アプリのサーバ（起動.bat の黒い画面）を停止してください。
echo.
echo 旧アプリのフォルダ（records.db があるフォルダ）、または records.db ファイルを
echo この画面にドラッグ＆ドロップして Enter を押してください。
echo.
set /p SRC="パス: "
set SRC=%SRC:"=%
if not exist ".venv\Scripts\python.exe" (
  echo .venv がありません。先に「初回セットアップ.bat」を実行してください。
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "tools\import_data.py" "%SRC%"
echo.
pause
