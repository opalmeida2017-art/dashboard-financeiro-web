@echo off
cd /d "%~dp0"
echo BIWEB teste local — http://127.0.0.1:5000
echo Nao encerra o python main.py do CT-e.
echo.
python run_dev.py
if errorlevel 1 pause
