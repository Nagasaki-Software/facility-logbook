@echo off
cd /d "%~dp0"
echo ==========================================
echo  統合アプリ（運転記録＋点検） 初回セットアップ
echo ==========================================
echo.
where python >nul 2>&1
if errorlevel 1 (
  echo [エラー] Python が見つかりません。
  echo https://www.python.org/ からインストールしてください。
  echo インストール時に「Add Python to PATH」へ必ずチェックを入れてください。
  pause
  exit /b 1
)
echo 仮想環境(.venv)を作成します...
python -m venv .venv
echo 必要なライブラリをインストールします（数分かかる場合があります）...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo [エラー] ライブラリのインストールに失敗しました。ネット接続を確認して再実行してください。
  pause
  exit /b 1
)
echo.
echo セットアップ完了。「起動.bat」をダブルクリックして開始してください。
pause
