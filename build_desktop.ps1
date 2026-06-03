# Gera BIWEB.exe e prepara pasta para instalador Inno Setup
# Uso: .\build_desktop.ps1

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Crie o venv: python -m venv .venv && .\.venv\Scripts\pip install -r requirements-desktop.txt"
    exit 1
}

$py = ".\.venv\Scripts\python.exe"
$pip = ".\.venv\Scripts\pip.exe"

& $pip install -q pyinstaller
& $py -m PyInstaller --noconfirm BIWEBDesktop.spec

$dist = Join-Path $Root "dist\BIWEB"
$out = Join-Path $Root "dist\BIWEB-pacote"
if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Path $out | Out-Null
Copy-Item $dist\* $out -Recurse -Force

$pgSrc = Join-Path $Root "runtime\postgresql"
if (Test-Path $pgSrc) {
    Copy-Item $pgSrc (Join-Path $out "runtime\postgresql") -Recurse -Force
    Write-Host "PostgreSQL portátil incluído."
} else {
    Write-Host "AVISO: runtime\postgresql não encontrado. Veja runtime\postgresql\README.md"
    New-Item -ItemType Directory -Path (Join-Path $out "runtime\postgresql") -Force | Out-Null
    Copy-Item (Join-Path $Root "runtime\postgresql\README.md") (Join-Path $out "runtime\postgresql\README.md") -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Pacote pronto em: $out"
Write-Host "Compile o instalador: iscc installer\biweb.iss"
