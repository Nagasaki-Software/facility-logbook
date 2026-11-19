@echo off
cd /d "%~dp0"
echo ==========================================
echo  [管理者用] 運転記録の確定解除
echo ==========================================
echo.
echo 確定済みの運転記録を一時的に編集可能へ戻します。
echo （解除後、アプリで修正し、再度「終了」で確定し直してください）
echo.
if not exist ".venv\Scripts\python.exe" (
  echo .venv がありません。先に「初回セットアップ.bat」を実行してください。
  pause
  exit /b 1
)
set /p RID="解除する記録IDを入力（複数はスペース区切り。空Enterで 確定解除リスト.txt を使用）: "
".venv\Scripts\python.exe" "tools\admin_unlock.py" %RID%
echo.
pause
