param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot '启动相机.ps1'
if (-not (Test-Path -LiteralPath $launcher)) { throw 'Camera launcher missing.' }
if ($CheckOnly) {
    $tokens=$null; $parseErrors=$null
    [System.Management.Automation.Language.Parser]::ParseFile($launcher,[ref]$tokens,[ref]$parseErrors) | Out-Null
    if ($parseErrors) { throw ($parseErrors | Out-String) }
    Write-Output 'PASS: camera CMD -> Windows PowerShell -> camera script. No device accessed.'
    exit 0
}
& $launcher -HardwareTrigger -TriggerSource Line2
