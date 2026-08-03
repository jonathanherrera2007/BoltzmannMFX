[CmdletBinding()]
param(
    [string]$SourceDir,
    [Parameter(Mandatory)][string]$BuildDir,
    [Parameter(Mandatory)][string]$OutputDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDir 'native_windows_env.ps1')
if (-not $SourceDir) { $SourceDir = (Resolve-Path (Join-Path $scriptDir '..\..')).Path }

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$source = Join-Path $SourceDir 'tools\repro\c10_plot_extract.cpp'
$object = Join-Path $OutputDir 'c10_plot_extract.obj'
$exe = Join-Path $OutputDir 'c10_plot_extract.exe'
$amrexBase = Join-Path $SourceDir 'subprojects\amrex\Src\Base'
$amrexBoundary = Join-Path $SourceDir 'subprojects\amrex\Src\Boundary'
$amrexAmrCore = Join-Path $SourceDir 'subprojects\amrex\Src\AmrCore'
$amrexEB = Join-Path $SourceDir 'subprojects\amrex\Src\EB'
$amrexMLMG = Join-Path $SourceDir 'subprojects\amrex\Src\LinearSolvers\MLMG'
$amrexParticle = Join-Path $SourceDir 'subprojects\amrex\Src\Particle'
$amrexGenerated = Join-Path $BuildDir 'subprojects\amrex'
$amrexLibrary = Join-Path $BuildDir 'subprojects\amrex\Src\amrex.lib'
$mpiInclude = 'C:\Program Files (x86)\Microsoft SDKs\MPI\Include'
$mpiLibrary = 'C:\Program Files (x86)\Microsoft SDKs\MPI\Lib\x64\msmpi.lib'

& $BmxTool.Cl /nologo /std:c++17 /EHsc /O2 /DNDEBUG /Zc:preprocessor /Zc:__cplusplus `
    "/I$amrexBase" "/I$amrexBoundary" "/I$amrexAmrCore" "/I$amrexEB" `
    "/I$amrexMLMG" "/I$amrexParticle" "/I$amrexGenerated" "/I$mpiInclude" `
    $source "/Fo$object" "/Fe$exe" $amrexLibrary $mpiLibrary
if ($LASTEXITCODE -ne 0) { throw "C10 plot extractor build failed: $LASTEXITCODE" }
Write-Host "C10 plot extractor: $exe"
