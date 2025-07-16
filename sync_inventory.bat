@echo off
chcp 65001 > nul
set /p commit_message="コミットメッセージを入力してください (例: 在庫データを更新): "

cd /d "%~dp0"

rem 仮想環境をアクティブ化
call venv\Scripts\activate

rem Gitコマンドを実行
git add .
git commit -m "%commit_message%"
git push origin main

rem 仮想環境を非アクティブ化
call deactivate

echo.
echo 在庫データの同期が完了しました！
pause
