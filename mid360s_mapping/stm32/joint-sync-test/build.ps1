param([string]$CompilerDirectory = 'E:/Keil5/Core/ARM/AC5/bin64')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
New-Item -ItemType Directory -Path 'build' -Force | Out-Null

function Invoke-CompilerTool {
    param([string]$Name, [string[]]$ToolArguments)
    & (Join-Path $CompilerDirectory $Name) @ToolArguments
    if ($LASTEXITCODE -ne 0) { throw "$Name failed with exit code $LASTEXITCODE" }
}

$objects = @()
$sources = @('main.c', 'rmc.c') + @(Get-ChildItem -LiteralPath 'vendor/src' -Filter '*.c' | ForEach-Object FullName)
foreach ($source in $sources) {
    $object = 'build/' + [IO.Path]::GetFileNameWithoutExtension($source) + '.o'
    Invoke-CompilerTool 'armcc.exe' @('--cpu=Cortex-M3', '--c99', '-O1', '-g',
        '-DSTM32F10X_MD', '-DUSE_STDPERIPH_DRIVER', '-Ivendor/inc', '-c', $source, '-o', $object)
    $objects += $object
}
Invoke-CompilerTool 'armasm.exe' @('--cpu=Cortex-M3', '-g',
    'vendor/src/startup_stm32f10x_hd.s', '-o', 'build/startup.o')
$objects += 'build/startup.o'
Invoke-CompilerTool 'armlink.exe' (@('--cpu=Cortex-M3', '--scatter=flash.sct',
    '--map', '--symbols', '--info=sizes', '--list=build/joint-sync-test.map',
    '-o', 'build/joint-sync-test.axf') + $objects)
Invoke-CompilerTool 'fromelf.exe' @('--i32combined', '--output=build/joint-sync-test.hex', 'build/joint-sync-test.axf')
Invoke-CompilerTool 'fromelf.exe' @('--bin', '--output=build/joint-sync-test.bin', 'build/joint-sync-test.axf')
Write-Output 'Build successful: build/joint-sync-test.hex'
