[CmdletBinding()]
param(
    [string]$SourceDir,
    [Parameter(Mandatory)][string]$BuildDir,
    [Parameter(Mandatory)][string]$RunDir,
    [string]$JsonOut
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDir 'native_windows_env.ps1')
if (-not $SourceDir) { $SourceDir = (Resolve-Path (Join-Path $scriptDir '..\..')).Path }

New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
$source = Join-Path $SourceDir 'tools\repro\c10_uptake_unit.cpp'
$object = Join-Path $RunDir 'c10_uptake_unit.obj'
$exe = Join-Path $RunDir 'c10_uptake_unit.exe'
$chemistry = Join-Path $SourceDir 'src\chemistry'
$amrexBase = Join-Path $SourceDir 'subprojects\amrex\Src\Base'
$amrexGenerated = Join-Path $BuildDir 'subprojects\amrex'

& $BmxTool.Cl /nologo /std:c++17 /EHsc "/I$chemistry" "/I$amrexBase" `
    "/I$amrexGenerated" $source "/Fo$object" "/Fe$exe"
if ($LASTEXITCODE -ne 0) { throw "C10 uptake unit compile failed: $LASTEXITCODE" }
$output = (& $exe 2>&1 | Out-String).Trim()
$exit = $LASTEXITCODE
Write-Host $output
if ($exit -ne 0) { throw "C10 uptake unit failed: $exit" }

if ($JsonOut) {
    $jsonPath = [System.IO.Path]::GetFullPath($JsonOut)
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $jsonPath) | Out-Null
    $status = if ($output -match '^C10_UPTAKE_UNIT PASS checks=(\d+)$') { 'PASS' } else { 'FAIL' }
    $record = [ordered]@{
        artifact_type = 'C10_UPTAKE_ANALYTICAL_UNIT'
        stage = 'C10/P12'
        status = $status
        checks_executed = if ($Matches.Count -gt 1) { [int]$Matches[1] } else { 0 }
        output = $output
        source_sha256 = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLower()
        header_sha256 = (Get-FileHash -LiteralPath (Join-Path $chemistry 'bmx_phosphorus_uptake_K.H') -Algorithm SHA256).Hash.ToLower()
        contract_sha256 = (Get-FileHash -LiteralPath (Join-Path $SourceDir 'contracts\p12\UPTAKE_ONLY_CONTRACT_V1.json') -Algorithm SHA256).Hash.ToLower()
        numerical_contract_sha256 = (Get-FileHash -LiteralPath (Join-Path $SourceDir 'contracts\p12\NUMERICAL_PREREGISTRATION_V2.json') -Algorithm SHA256).Hash.ToLower()
        executable_sha256 = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLower()
        external_resources = 'none'
        external_spend_usd = 0
        claim_boundary = 'Pure deterministic analytical transaction tests; no native depletion claim, calibration, or release-host evidence.'
    }
    [System.IO.File]::WriteAllText($jsonPath, (($record | ConvertTo-Json -Depth 8) + [Environment]::NewLine), [System.Text.UTF8Encoding]::new($false))
    if ($status -ne 'PASS') { throw 'C10 unit output was not canonical PASS' }
}
