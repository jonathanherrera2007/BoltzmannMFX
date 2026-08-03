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
if (-not $SourceDir) {
    $SourceDir = (Resolve-Path (Join-Path $scriptDir '..\..')).Path
}

New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
$source = Join-Path $SourceDir 'tools\repro\c12_export_unit.cpp'
$object = Join-Path $RunDir 'c12_export_unit.obj'
$exe = Join-Path $RunDir 'c12_export_unit.exe'
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
if ($LASTEXITCODE -ne 0) {
    throw "C12 export unit compile failed: $LASTEXITCODE"
}
$output = (& $exe 2>&1 | Out-String).Trim()
$exit = $LASTEXITCODE
Write-Host $output
if ($exit -ne 0) { throw "C12 export unit failed: $exit" }

if ($JsonOut) {
    $jsonPath = [System.IO.Path]::GetFullPath($JsonOut)
    New-Item -ItemType Directory -Force -Path (
        Split-Path -Parent $jsonPath
    ) | Out-Null
    $matched = [regex]::Match(
        $output, '^C12_EXPORT_UNIT PASS checks=(\d+)$'
    )
    $status = if ($matched.Success) { 'PASS' } else { 'FAIL' }
    $record = [ordered]@{
        artifact_type = 'C12_P14_ANALYTICAL_UNIT'
        stage = 'C12/P14'
        status = $status
        checks_executed = if ($matched.Success) {
            [int]$matched.Groups[1].Value
        } else { 0 }
        output = $output
        source_sha256 = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLower()
        header_sha256 = (Get-FileHash -LiteralPath (
            Join-Path $SourceDir 'src\chemistry\bmx_phosphorus_export_K.H'
        ) -Algorithm SHA256).Hash.ToLower()
        contract_sha256 = (Get-FileHash -LiteralPath (
            Join-Path $SourceDir 'contracts\p14\EXPORT_REWARD_CONTRACT_V1.json'
        ) -Algorithm SHA256).Hash.ToLower()
        operator_fit_sha256 = (Get-FileHash -LiteralPath (
            Join-Path $SourceDir 'contracts\p14\OPERATOR_FIT_V1.json'
        ) -Algorithm SHA256).Hash.ToLower()
        frozen_global_order_sha256 = (Get-FileHash -LiteralPath (
            Join-Path $SourceDir 'contracts\p10\OPERATOR_ORDER_V1.json'
        ) -Algorithm SHA256).Hash.ToLower()
        frozen_kernel_sha256 = (Get-FileHash -LiteralPath (
            Join-Path $SourceDir 'src\chemistry\bmx_chem_K.H'
        ) -Algorithm SHA256).Hash.ToLower()
        external_resources = 'none'
        external_spend_usd = 0
        claim_boundary = 'Deterministic analytical P14 geometry and transaction tests only; not mentor approval, calibration, predictive validation, or C13 science.'
    }
    [System.IO.File]::WriteAllText(
        $jsonPath,
        (($record | ConvertTo-Json -Depth 8) + [Environment]::NewLine),
        [System.Text.UTF8Encoding]::new($false)
    )
    if ($status -ne 'PASS') { throw 'C12 unit output was not canonical PASS' }
}
