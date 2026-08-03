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
$source = Join-Path $SourceDir 'tools\repro\c13_p15_unit.cpp'
$object = Join-Path $RunDir 'c13_p15_unit.obj'
$exe = Join-Path $RunDir 'c13_p15_unit.exe'
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
    throw "C13 P15 analytical unit compile failed: $LASTEXITCODE"
}
$output = (& $exe 2>&1 | Out-String).Trim()
$exit = $LASTEXITCODE
Write-Host $output
if ($exit -ne 0) { throw "C13 P15 analytical unit failed: $exit" }

if ($JsonOut) {
    $jsonPath = [System.IO.Path]::GetFullPath($JsonOut)
    New-Item -ItemType Directory -Force -Path (
        Split-Path -Parent $jsonPath
    ) | Out-Null
    $matched = [regex]::Match(
        $output, '^C13_P15_UNIT PASS checks=(\d+)$'
    )
    $status = if ($matched.Success) { 'PASS' } else { 'FAIL' }
    $record = [ordered]@{
        artifact_type = 'C13_P15_ANALYTICAL_STAGE0_UNIT'
        stage = 'C13/P15 Stage 0'
        status = $status
        checks_executed = if ($matched.Success) {
            [int]$matched.Groups[1].Value
        } else { 0 }
        fixtures = @(
            'unequal-radius unequal-length degree-two conductance',
            'degree-three junction elimination',
            'degree-four junction elimination',
            'two-segment exponential-equilibration convergence',
            'exact D_bond=0 arithmetic identity',
            'pairwise and global conservation',
            'positivity and no-new-extremum',
            'proportional donor arbitration and cap ledger',
            'isolated/simple/branch/tie/partial/two-ended terminal geometry',
            '1-to-2, 1-to-4, and 1-to-8 representation refinement',
            'invalid and nonfinite operands'
        )
        output = $output
        source_sha256 = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLower()
        header_sha256 = (Get-FileHash -LiteralPath (
            Join-Path $SourceDir 'src\chemistry\bmx_p15_stage0_K.H'
        ) -Algorithm SHA256).Hash.ToLower()
        bonded_contract_sha256 = (Get-FileHash -LiteralPath (
            Join-Path $SourceDir 'contracts\p15\BONDED_D_TRANSPORT_CONTRACT_V1.json'
        ) -Algorithm SHA256).Hash.ToLower()
        terminal_contract_sha256 = (Get-FileHash -LiteralPath (
            Join-Path $SourceDir 'contracts\p15\TERMINAL_ZONE_CONTRACT_V1.json'
        ) -Algorithm SHA256).Hash.ToLower()
        numerical_contract_sha256 = (Get-FileHash -LiteralPath (
            Join-Path $SourceDir 'contracts\p15\NUMERICAL_PREREGISTRATION_V1.json'
        ) -Algorithm SHA256).Hash.ToLower()
        frozen_global_order_sha256 = (Get-FileHash -LiteralPath (
            Join-Path $SourceDir 'contracts\p10\OPERATOR_ORDER_V1.json'
        ) -Algorithm SHA256).Hash.ToLower()
        frozen_kernel_sha256 = (Get-FileHash -LiteralPath (
            Join-Path $SourceDir 'src\chemistry\bmx_chem_K.H'
        ) -Algorithm SHA256).Hash.ToLower()
        outcome_hours = 0
        independent_review_gate_crossed = $false
        external_resources = 'none'
        external_spend_usd = 0
        claim_boundary = 'Deterministic C13 Stage 0 analytical engineering tests only; not a 216-hour outcome, mentor approval, calibration, predictive validation, or science.'
    }
    [System.IO.File]::WriteAllText(
        $jsonPath,
        (($record | ConvertTo-Json -Depth 8) + [Environment]::NewLine),
        [System.Text.UTF8Encoding]::new($false)
    )
    if ($status -ne 'PASS') { throw 'C13 unit output was not canonical PASS' }
}
