param([switch]$HardwareTrigger,
      [ValidateSet('Line1','Line2')][string]$TriggerSource='Line2')
$ErrorActionPreference = 'Stop'
# Keep WSL alive while usbipd negotiates. This helper exits after 60 seconds;
# once capture starts the camera process itself keeps the distribution running.
Start-Process -FilePath 'wsl.exe' -WindowStyle Hidden -ArgumentList '-d Ubuntu-22.04 -- sleep 60'
& wsl.exe -d Ubuntu-22.04 -- true
if ($LASTEXITCODE -ne 0) { throw 'WSL startup failed.' }
$usbipd = 'C:\Program Files\usbipd-win\usbipd.exe'
$state = & $usbipd state | ConvertFrom-Json
$camera = @($state.Devices | Where-Object { $_.InstanceId -eq 'USB\VID_2E03&PID_0001\DD07657AAK00023' })
if ($camera.Count -ne 1 -or -not $camera[0].BusId) { throw 'Camera DD07657AAK00023 is not connected.' }
if (-not $camera[0].ClientIPAddress) {
    & $usbipd attach --wsl Ubuntu-22.04 --busid $camera[0].BusId
    if ($LASTEXITCODE -ne 0) { throw 'USB attach failed. Close MVviewer and check usbipd list.' }
}
$captureArguments = @('--ros-args', '-p', 'exposure_us:=30000.0', '-p', 'gain:=2.0')
if ($HardwareTrigger) {
    $captureArguments += @('-p', 'hardware_trigger:=true', '-p', "trigger_source:=$TriggerSource", '-p', 'expected_frames:=10', '-p', 'seconds:=180.0')
}
& wsl.exe -d Ubuntu-22.04 -- bash /mnt/e/chatgpt_project/mid360s_mapping/camera/run-camera.sh @captureArguments
if ($LASTEXITCODE -ne 0) { throw 'Camera acquisition failed; see latest capture console.log.' }
