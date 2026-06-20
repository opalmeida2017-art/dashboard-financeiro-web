# Recria o venv após corrupção acidental (rewrite_imports no site-packages).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "Removendo venv antigo..."
if (Test-Path venv) { Remove-Item -Recurse -Force venv }

Write-Host "Criando venv novo..."
python -m venv venv

Write-Host "Instalando dependencias..."
.\venv\Scripts\pip.exe install --upgrade pip
.\venv\Scripts\pip.exe install -r requirements.txt

Write-Host "Pronto. Suba com: python run_dev.py"
