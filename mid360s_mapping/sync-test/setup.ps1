param([string]$Python='C:\Users\31289\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    & $Python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' }
}
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'pyserial installation failed' }
