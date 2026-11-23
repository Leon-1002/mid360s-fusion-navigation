$ErrorActionPreference = 'Stop'
$usbipd = 'C:\Program Files\usbipd-win\usbipd.exe'
$state = & $usbipd state | ConvertFrom-Json
$camera = @($state.Devices | Where-Object { $_.InstanceId -eq 'USB\VID_2E03&PID_0001\DD07657AAK00023' })
if ($camera.Count -ne 1 -or -not $camera[0].BusId) {
    throw 'Expected camera DD07657AAK00023 is not connected uniquely.'
}
$state | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'usb-before-sharing.json') -Encoding UTF8
& $usbipd bind --busid $camera[0].BusId
if ($LASTEXITCODE -ne 0) { throw 'Camera USB sharing failed.' }
& $usbipd state | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'usb-after-sharing.json') -Encoding UTF8
Write-Host 'Camera USB sharing is ready.'
