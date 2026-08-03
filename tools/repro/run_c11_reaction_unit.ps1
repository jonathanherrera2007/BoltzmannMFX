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
$source = Join-Path $SourceDir 'tools\repro\c11_reaction_unit.cpp'
$object = Join-Path $RunDir 'c11_reaction_unit.obj'
$exe = Join-Path $RunDir 'c11_reaction_unit.exe'
$includes = @(
    (Join-Path $SourceDir 'src'),
    (Join-Path $SourceDir 'src\chemistry'),
    (Join-Path $SourceDir 'src\des'),
    (Join-Path $SourceDir 'subprojects\amrex\Src\Base'),
    (Join-Path $SourceDir 'subprojects\amrex\Src\Base\Parser'),
    (Join-Path $BuildDir 'subprojects\amrex'),
    $BmxTool.MpiInc
)
$includeArgs = @($includes | ForEach-Object { "/I$_" })

& $BmxTool.Cl /nologo /std:c++17 /Zc:preprocessor /Zc:__cplusplus /EHsc `
    /DWIN32 /D_WINDOWS /D_USE_MATH_DEFINES @includeArgs $source `
    "/Fo$object" "/Fe$exe"
if ($LASTEXITCODE -ne 0) { throw "C11 reaction unit compile failed: $LASTEXITCODE" }
$output = (& $exe 2>&1 | Out-String).Trim()
$exit = $LASTEXITCODE
Write-Host $output
if ($exit -ne 0) { throw "C11 reaction unit failed: $exit" }

if ($JsonOut) {
    $jsonPath = [System.IO.Path]::GetFullPath($JsonOut)
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $jsonPath) | Out-Null
    $status = if ($output -match '^C11_REACTION_UNIT PASS checks=(\d+)$') { 'PASS' } else { 'FAIL' }
    $record = [ordered]@{
        artifact_type = 'C11_P13_ANALYTICAL_UNIT'
        stage = 'C11/P13'
        status = $status
        checks_executed = if ($Matches.Count -gt 1) { [int]$Matches[1] } else { 0 }
        output = $output
        source_sha256 = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLower()
        header_sha256 = (Get-FileHash -LiteralPath (Join-Path $SourceDir 'src\chemistry\bmx_phosphorus_reactions_K.H') -Algorithm SHA256).Hash.ToLower()
        contract_sha256 = (Get-FileHash -LiteralPath (Join-Path $SourceDir 'contracts\p13\REACTION_LIEBIG_CONTRACT_V1.json') -Algorithm SHA256).Hash.ToLower()
        operator_fit_sha256 = (Get-FileHash -LiteralPath (Join-Path $SourceDir 'contracts\p13\OPERATOR_FIT_V1.json') -Algorithm SHA256).Hash.ToLower()
        frozen_global_order_sha256 = (Get-FileHash -LiteralPath (Join-Path $SourceDir 'contracts\p10\OPERATOR_ORDER_V1.json') -Algorithm SHA256).Hash.ToLower()
        frozen_kernel_sha256 = (Get-FileHash -LiteralPath (Join-Path $SourceDir 'src\chemistry\bmx_chem_K.H') -Algorithm SHA256).Hash.ToLower()
        external_resources = 'none'
        external_spend_usd = 0
        claim_boundary = 'Deterministic analytical P13 transaction tests only; no biological baseline, calibration, prediction, or C12+ behavior.'
    }
    [System.IO.File]::WriteAllText($jsonPath, (($record | ConvertTo-Json -Depth 8) + [Environment]::NewLine), [System.Text.UTF8Encoding]::new($false))
    if ($status -ne 'PASS') { throw 'C11 unit output was not canonical PASS' }
}
