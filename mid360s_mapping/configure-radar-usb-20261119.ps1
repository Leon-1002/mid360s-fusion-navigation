$ErrorActionPreference = 'Stop'
$resultPath = Join-Path $PSScriptRoot 'usb-ethernet-result-20261119.json'
try {
    $adapter = Get-NetAdapter -InterfaceIndex 38
    if ($adapter.MacAddress -ne 'EC-1A-C3-17-A9-9F' -or $adapter.InterfaceDescription -notlike 'ASIX AX88179*') {
        throw 'USB adapter identity changed; configuration was not modified.'
    }
    $existing = Get-NetIPAddress -InterfaceIndex 38 -AddressFamily IPv4
    if (-not ($existing | Where-Object { $_.IPAddress -eq '192.168.1.50' -and $_.PrefixLength -eq 24 })) {
        New-NetIPAddress -InterfaceIndex 38 -IPAddress 192.168.1.50 -PrefixLength 24 -AddressFamily IPv4 | Out-Null
    }
    $addresses = @(Get-NetIPAddress -InterfaceIndex 38 -AddressFamily IPv4 | Select-Object IPAddress,PrefixLength)
    @{success=$true; adapter=$adapter.Name; addresses=$addresses} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $resultPath -Encoding UTF8
    Write-Host 'Radar USB adapter configured: 192.168.1.50/24'
} catch {
    @{success=$false; error=$_.Exception.Message} | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
    Write-Error $_
    exit 1
}
