param([string]$Port='COM8')
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$active=& wsl.exe -d Ubuntu-22.04 -u leon -- pgrep -af '[f]astlio_mapping|[l]ivox_ros_driver2_node|[r]os2 bag record'
if ($LASTEXITCODE -ne 1) { throw "Acquisition preflight not clear; no joint test started. $active" }
if (Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -Match 'MVviewer|Livox.*Viewer') {
    throw 'Close MV Viewer and Livox Viewer before starting this test.'
}
& "$PSScriptRoot\.venv\Scripts\python.exe" "$PSScriptRoot\joint_test.py" --port $Port
if ($LASTEXITCODE -eq 3) {
    Write-Warning 'Joint timing/count checks passed. Point cloud payload CRC remains unavailable; real UTC and ROS transport are not tested.'
    exit 3
}
if ($LASTEXITCODE -ne 0) { throw 'Joint test did not pass; inspect the printed report folder.' }
