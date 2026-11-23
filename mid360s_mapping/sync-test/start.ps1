param(
    [ValidateSet('menu','serial','probe','sync')][string]$Mode='menu',
    [string]$Port='',
    [int]$Seconds=60,
    [switch]$CheckOnly
)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$python=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run setup.ps1 first.' }
if ($CheckOnly) {
    & $python -c "import serial; import livox_wire; print('PASS: radar CMD -> Windows PowerShell -> Python dependencies. No device accessed.')"
    if ($LASTEXITCODE -ne 0) { throw 'Dependency check failed.' }
    exit 0
}
if ($Mode -eq 'menu') {
    Write-Host '1. Serial test only (no network writes)'
    Write-Host '2. Radar network/status query only'
    Write-Host '3. PPS + RMC -> Ethernet synchronization test (synthetic time)'
    Write-Host 'Close Livox Viewer / FAST-LIO / ROS lidar driver before 2 or 3.'
    $selection=Read-Host 'Choose 1 / 2 / 3'
    $Mode=switch ($selection) { '1' {'serial'} '2' {'probe'} '3' {'sync'} default {throw 'Invalid selection'} }
}
if ($Mode -ne 'serial') {
    $active = & wsl.exe -d Ubuntu-22.04 -u leon -- pgrep -af '[f]astlio_mapping|[l]ivox_ros_driver2_node|[r]os2 bag record'
    $pgrepResult=$LASTEXITCODE
    if ($pgrepResult -eq 0) { throw "Stop existing mapping/driver/recorder first. No process was killed: $active" }
    if ($pgrepResult -ne 1) { throw 'Could not verify WSL acquisition state. No time command sent.' }
    if (Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -Match 'Livox.*Viewer|LivoxViewer') {
        throw 'Close Livox Viewer first.'
    }
}
$arguments=@('run_sync.py','--mode',$Mode,'--seconds',"$Seconds")
if ($Port) { $arguments+=@('--port',$Port) }
& $python @arguments
if ($LASTEXITCODE -eq 3) {
    Write-Warning 'Timing checks passed, but point payload CRC is unavailable. This is a limited timing result, not full integrity acceptance. See summary.json.'
    exit 3
}
if ($LASTEXITCODE -ne 0) { throw 'Test incomplete or failed. See the printed sessions directory; do not treat as synchronized.' }
