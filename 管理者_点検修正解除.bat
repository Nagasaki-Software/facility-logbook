@echo off
cd /d "%~dp0"
echo ==========================================
echo  [管理者用] 過去の点検結果の 修正解除 / 削除
echo ==========================================
echo.
echo  1 : 編集可にする（修正解除）… 修正後アプリで上書き保存
echo  2 : 削除する … その点検を完全に削除（元に戻せません）
echo.
if not exist ".venv\Scripts\python.exe" (
  echo .venv がありません。先に「初回セットアップ.bat」を実行してください。
  pause
  exit /b 1
)
set /p MODE="番号を入力（1=編集可 / 2=削除）: "
if "%MODE%"=="2" goto DELETE
goto UNLOCK

:DELETE
set /p IID="削除する点検IDを入力（複数はスペース区切り）: "
".venv\Scripts\python.exe" "tools\check_unlock.py" --delete %IID%
goto END

:UNLOCK
set /p IID="編集可にする点検IDを入力（複数はスペース区切り。空Enterで 点検修正リスト.txt を使用）: "
".venv\Scripts\python.exe" "tools\check_unlock.py" %IID%
goto END

:END
echo.
pause
