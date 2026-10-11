param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$venvRuntime = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
$localDependencies = Join-Path $PSScriptRoot '.deps'
if (Test-Path -LiteralPath $venvRuntime) {
    $chatRuntime = $venvRuntime
} elseif ((Test-Path -LiteralPath $localDependencies) -and (Test-Path -LiteralPath 'D:/python/python.exe')) {
    # This checkout's verification dependencies were installed for this runtime.
    $chatRuntime = 'D:/python/python.exe'
    $env:PYTHONPATH = $localDependencies
} else {
    $chatRuntime = 'python'
}
# Local demo uses one process and never connects to the old conversation database.
$env:MEMORY_BACKEND = 'memory'
Write-Host "Open http://127.0.0.1:$Port in your browser. Press Ctrl+C to stop."
& $chatRuntime -m uvicorn main:app --host 127.0.0.1 --port $Port
