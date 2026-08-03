[CmdletBinding()]
param(
    [string]$SourceDir,
    [string]$BuildDir,
    [string]$RunDir,
    [string]$JsonOut
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDir 'native_windows_env.ps1')

if (-not $SourceDir) {
    $SourceDir = (Resolve-Path (Join-Path $scriptDir '..\..')).Path
}
if (-not $BuildDir) {
    throw 'BuildDir is required so the generated AMReX configuration is exact.'
}
if (-not $RunDir) {
    $RunDir = Join-Path (Split-Path -Parent $SourceDir) 'runs\c09-geometry-unit'
}

New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
$object = Join-Path $RunDir 'c09_geometry_unit.obj'
$exe = Join-Path $RunDir 'c09_geometry_unit.exe'
$source = Join-Path $SourceDir 'tools\repro\c09_geometry_unit.cpp'
$chemistry = Join-Path $SourceDir 'src\chemistry'
$amrexBase = Join-Path $SourceDir 'subprojects\amrex\Src\Base'
$amrexGenerated = Join-Path $BuildDir 'subprojects\amrex'

& $BmxTool.Cl /nologo /std:c++17 /EHsc "/I$chemistry" "/I$amrexBase" `
    "/I$amrexGenerated" $source "/Fo$object" "/Fe$exe"
if ($LASTEXITCODE -ne 0) {
    throw "C09 geometry unit compile failed with exit code $LASTEXITCODE"
}

$unitOutput = (& $exe 2>&1 | Out-String).Trim()
$unitExit = $LASTEXITCODE
Write-Host $unitOutput
if ($unitExit -ne 0) { throw "C09 geometry unit failed with exit code $unitExit" }

if ($JsonOut) {
    $jsonPath = [System.IO.Path]::GetFullPath($JsonOut)
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $jsonPath) | Out-Null
    $record = [ordered]@{
        artifact_type = 'C09_GEOMETRY_UNIT_TEST'
        stage = 'C09/P11'
        status = if ($unitOutput -match '^C09_GEOMETRY_UNIT PASS checks=(\d+)$') { 'PASS' } else { 'FAIL' }
        checks_executed = if ($Matches.Count -gt 1) { [int]$Matches[1] } else { 0 }
        output = $unitOutput
        executable = [ordered]@{
            path = $exe
            sha256 = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLower()
        }
        source_sha256 = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLower()
        geometry_header_sha256 = (Get-FileHash -LiteralPath (Join-Path $chemistry 'bmx_phosphorus_geometry_K.H') -Algorithm SHA256).Hash.ToLower()
        external_resources = 'none'
        external_spend_usd = 0
        claim_boundary = 'Pure deterministic C09 engineering predicates; no biological calibration, reference-host evidence, or independent numerical review.'
    }
    [System.IO.File]::WriteAllText(
        $jsonPath,
        (($record | ConvertTo-Json -Depth 8) + [Environment]::NewLine),
        [System.Text.UTF8Encoding]::new($false)
    )
    if ($record.status -ne 'PASS') { throw 'C09 geometry unit output was not canonical PASS' }
}

Write-Host "geometry unit executable: $exe"
