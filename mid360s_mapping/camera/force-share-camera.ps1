$ErrorActionPreference = 'Stop'
$usbipd = 'C:\Program Files\usbipd-win\usbipd.exe'
$state = & $usbipd state | ConvertFrom-Json
$camera = @($state.Devices | Where-Object { $_.InstanceId -eq 'USB\VID_2E03&PID_0001\DD07657AAK00023' })
if ($camera.Count -ne 1 -or -not $camera[0].BusId) { throw 'Target camera is not connected.' }
$state | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $PSScriptRoot ('usb-before-force-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json'))
& $usbipd bind --force --busid $camera[0].BusId
if ($LASTEXITCODE -ne 0) { throw 'Force binding failed.' }
& $usbipd state | Set-Content (Join-Path $PSScriptRoot 'usb-after-force.json')
Write-Host 'Camera-only binding complete. Roll back using usbipd unbind --busid <current camera BUSID>.'
