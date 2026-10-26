@echo off
cd /d "%~dp0"
echo Puxa a versao do GitHub e reinicia o BIWEB de teste (esta pasta).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\atualizar_do_github.ps1"
if errorlevel 1 pause & exit /b 1
echo.
echo Painel: http://127.0.0.1:5000
pause
