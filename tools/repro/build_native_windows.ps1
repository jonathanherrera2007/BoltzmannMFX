# BMX RG-SW — build the configured native Windows tree.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File build_native_windows.ps1 `
#              [-BuildDir <path>] [-Target bmx] [-Parallel 8]

[CmdletBinding()]
param(
    [string]$BuildDir,
    [string]$Target = 'bmx',
    [int]$Parallel = 8
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDir 'native_windows_env.ps1')

if (-not $BuildDir) {
    $sourceDir = (Resolve-Path (Join-Path $scriptDir '..\..')).Path
    $BuildDir  = Join-Path (Split-Path -Parent (Split-Path -Parent $sourceDir)) 'build\c02-native-release'
}
if (-not (Test-Path -LiteralPath (Join-Path $BuildDir 'CMakeCache.txt'))) {
    throw "build directory is not configured (no CMakeCache.txt): $BuildDir`nRun configure_native_windows.ps1 first."
}

Write-Host "build  : $BuildDir"
Write-Host "target : $Target"

$sw = [Diagnostics.Stopwatch]::StartNew()
& $BmxTool.CMake --build $BuildDir --config Release --target $Target --parallel $Parallel
if ($LASTEXITCODE -ne 0) { throw "build failed with exit code $LASTEXITCODE" }
$sw.Stop()

$exe = Join-Path $BuildDir 'bmx.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw "build reported success but $exe is absent" }

$hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLower()
Write-Host ''
Write-Host "build OK in $([int]$sw.Elapsed.TotalSeconds) s"
Write-Host "executable   : $exe"
Write-Host "size_bytes   : $((Get-Item -LiteralPath $exe).Length)"
Write-Host "sha256       : $hash"
