@echo off
cd /d "%~dp0"
echo Envia a versao atual desta pasta para o GitHub (branch main).
echo Depois rode atualizar_do_github.bat nesta maquina, ou o workflow self-hosted.
echo.
git status -sb
echo.
set /p MSG=Mensagem do commit (Enter = publicar versao BIWEB): 
if "%MSG%"=="" set MSG=Publicar versao BIWEB de teste
git add -A
git reset HEAD -- .env .venv venv deploy downloads __pycache__ >nul 2>&1
git commit -m "%MSG%"
if errorlevel 1 (
  echo Nada novo para commitar, so push.
)
git push origin main
if errorlevel 1 pause & exit /b 1
echo.
echo GitHub atualizado. Para reiniciar o teste local: atualizar_do_github.bat
pause
