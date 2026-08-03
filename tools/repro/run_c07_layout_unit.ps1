# Compile and execute the standalone C07 layout/map contract unit.
[CmdletBinding()]
param(
    [string]$SourceDir,
    [string]$RunDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDir 'native_windows_env.ps1')

if (-not $SourceDir) { $SourceDir = (Resolve-Path (Join-Path $scriptDir '..\..')).Path }
if (-not $RunDir) { $RunDir = Join-Path (Split-Path -Parent $SourceDir) 'runs\c07-layout-unit' }

New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
$object = Join-Path $RunDir 'c07_layout_unit.obj'
$exe = Join-Path $RunDir 'c07_layout_unit.exe'
$include = Join-Path $SourceDir 'src\chemistry'
$source = Join-Path $SourceDir 'tools\repro\c07_layout_unit.cpp'

& $BmxTool.Cl /nologo /std:c++17 /EHsc "/I$include" $source "/Fo$object" "/Fe$exe"
if ($LASTEXITCODE -ne 0) { throw "C07 layout unit compile failed with exit code $LASTEXITCODE" }

& $exe
if ($LASTEXITCODE -ne 0) { throw "C07 layout unit failed with exit code $LASTEXITCODE" }

Write-Host "layout unit executable: $exe"
