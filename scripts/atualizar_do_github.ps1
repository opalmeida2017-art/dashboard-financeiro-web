# Puxa a main do GitHub e reinicia só o run_dev.py deste BIWEB.
# Nao mata o python main.py do CTe nem outros processos.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "=== BIWEB teste: git pull origin main ==="
git fetch origin main
git pull --ff-only origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO: pull nao foi fast-forward. Resolva o git local e tente de novo."
    exit 1
}

$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = Join-Path $Root "venv\Scripts\python.exe" }
if (-not (Test-Path $Py)) { $Py = "python" }

Write-Host "=== dependencias ==="
& $Py -m pip install -q -r (Join-Path $Root "requirements.txt")

$runDev = Join-Path $Root "run_dev.py"
$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" |
    Where-Object { $_.CommandLine -and $_.CommandLine -match [regex]::Escape($runDev) }
foreach ($p in $procs) {
    Write-Host "Encerrando run_dev.py PID $($p.ProcessId)"
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}

Write-Host "=== subir teste http://127.0.0.1:5000 ==="
Start-Process -FilePath $Py -ArgumentList "run_dev.py" -WorkingDirectory $Root -WindowStyle Minimized
Start-Sleep -Seconds 2
Write-Host "OK. Versao:"
Get-Content (Join-Path $Root "VERSION") -ErrorAction SilentlyContinue
git -C $Root log -1 --oneline
