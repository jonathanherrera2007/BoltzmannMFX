# Compile and execute the standalone C08 amount/topology helper unit.
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

if (-not $SourceDir) { $SourceDir = (Resolve-Path (Join-Path $scriptDir '..\..')).Path }
if (-not $BuildDir) { $BuildDir = Join-Path (Split-Path -Parent $SourceDir) 'build-c07-native-release' }
if (-not $RunDir) { $RunDir = Join-Path (Split-Path -Parent $SourceDir) 'runs\c08-amount-unit' }

New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
$object = Join-Path $RunDir 'c08_amount_unit.obj'
$exe = Join-Path $RunDir 'c08_amount_unit.exe'
$source = Join-Path $SourceDir 'tools\repro\c08_amount_unit.cpp'

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
if ($LASTEXITCODE -ne 0) { throw "C08 amount unit compile failed with exit code $LASTEXITCODE" }

& $exe
if ($LASTEXITCODE -ne 0) { throw "C08 amount unit failed with exit code $LASTEXITCODE" }

Write-Host "amount unit executable: $exe"

if ($JsonOut) {
    $jsonPath = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $JsonOut))
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $jsonPath) | Out-Null
    $record = [ordered]@{
        artifact_type = 'C08_AMOUNT_HELPER_UNIT'
        stage = 'C08'
        status = 'PASS'
        source = [ordered]@{
            path = [System.IO.Path]::GetFullPath($source)
            sha256 = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLower()
        }
        executable = [ordered]@{
            path = [System.IO.Path]::GetFullPath($exe)
            sha256 = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLower()
        }
        assertions = @(
            'two-way partition preserves committed, working, and signed-transfer D/E/F amounts'
            'three-way partition preserves committed, working, and signed-transfer D/E/F amounts'
            'additive merge preserves D/E/F amounts'
            'one-owner pure-volume restore preserves D/E/F amounts after owning volume changes'
            'non-phosphorus sentinels remain unchanged'
            'zero owning volume, nonfinite state, overflow, and negative committed inventory fail closed'
            'local and integrated tolerance formulas match the frozen P10-U03 contract'
            'global accounted-total formula includes mesh D/F, internal D/E/F, structural P, and export exactly once while v1 other exits remain zero'
            'orphan-bond and simultaneous-event policy returns the adopted exact reason codes and fail-closed dispositions'
        )
        claim_boundary = 'analytic engineering unit; no biological values or final-run qualification'
    }
    $jsonText = ($record | ConvertTo-Json -Depth 6) + [Environment]::NewLine
    [System.IO.File]::WriteAllText(
        $jsonPath,
        $jsonText,
        [System.Text.UTF8Encoding]::new($false)
    )
    Write-Host "amount unit evidence: $jsonPath"
}
