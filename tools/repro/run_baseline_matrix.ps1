# BMX RG-SW — C03 lean baseline run matrix.
#
# Executes the untouched canonical source (baseline worktree, no P07 repair) over
# a small ordered matrix, captures raw stdout, and hashes every artefact.
#
# This is a LEAN product-oriented baseline. It deliberately does NOT reproduce the
# Control Tower P06 package structure (authorisation receipts, nonces,
# protected-path proofs). It does not and cannot claim official P06 acceptance.
#
# Nothing here is a scientific result. The matrix exists to (a) prove the
# untouched build runs the paths P07 will touch, and (b) give C05 a raw
# baseline to compare the repaired tree against.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File run_baseline_matrix.ps1 `
#              [-BuildDir <path>] [-SourceDir <path>] [-OutRoot <path>]

[CmdletBinding()]
param(
    [string]$BuildDir,
    [string]$SourceDir,
    [string]$OutRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDir 'native_windows_env.ps1')

$rgswRoot = Split-Path -Parent (Split-Path -Parent (Resolve-Path (Join-Path $scriptDir '..\..')).Path)
if (-not $SourceDir) { $SourceDir = Join-Path $rgswRoot 'worktrees\baseline' }
if (-not $BuildDir)  { $BuildDir  = Join-Path $rgswRoot 'build\c03-baseline-release' }
if (-not $OutRoot)   { $OutRoot   = Join-Path $rgswRoot 'runs\c03-baseline' }

$exe = Join-Path $BuildDir 'bmx.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw "baseline executable not found: $exe" }
$caseDir = Join-Path $SourceDir 'exec\fungi'

$exeHash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLower()
Write-Host "baseline exe : $exe"
Write-Host "sha256       : $exeHash"
Write-Host "case dir     : $caseDir"
Write-Host "out root     : $OutRoot"
Write-Host ''

if (Test-Path -LiteralPath $OutRoot) { Remove-Item -LiteralPath $OutRoot -Recurse -Force }
New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null

# Ordered matrix. Every case pins the seed explicitly rather than relying on the
# inputs file, so the run index records the seed actually used.
$matrix = @(
    @{ id='B01_init_only';      desc='initialisation only';                      ranks=1; args=@('bmx.max_step=0','bmx.seed=43343') },
    @{ id='B02_steps20';        desc='20 steps, canonical seed';                 ranks=1; args=@('bmx.max_step=20','bmx.seed=43343') },
    @{ id='B03_steps20_rerun';  desc='exact rerun of B02 (determinism)';         ranks=1; args=@('bmx.max_step=20','bmx.seed=43343') },
    @{ id='B04_steps20_seed2';  desc='20 steps, alternate seed';                 ranks=1; args=@('bmx.max_step=20','bmx.seed=21893') },
    @{ id='B05_ckpt_write';     desc='10 steps, write checkpoint at 10';         ranks=1; args=@('bmx.max_step=10','bmx.seed=43343','amr.check_int=10','amr.check_file=chk') },
    @{ id='B06_ckpt_restart';   desc='restart from chk00010, continue to 20';    ranks=1; args=@('bmx.max_step=20','bmx.seed=43343','amr.restart=chk00010') },
    @{ id='B07_steps20_2rank';  desc='20 steps under 2 MPI ranks';               ranks=2; args=@('bmx.max_step=20','bmx.seed=43343') },
    @{ id='B08_steps200_growth';desc='200 steps, exercises split/fusion/growth'; ranks=1; args=@('bmx.max_step=200','bmx.seed=43343') }
)

$index = @()

foreach ($case in $matrix) {
    $dir = Join-Path $OutRoot $case.id
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    Copy-Item -LiteralPath (Join-Path $caseDir 'input_fungi')        -Destination $dir
    Copy-Item -LiteralPath (Join-Path $caseDir 'fungi_init_cfg.dat') -Destination $dir

    # B06 restarts from the checkpoint B05 wrote. Copy it in rather than sharing a
    # directory, so every case stays independently re-runnable from its own inputs.
    if ($case.id -eq 'B06_ckpt_restart') {
        $src = Join-Path (Join-Path $OutRoot 'B05_ckpt_write') 'chk00010'
        if (-not (Test-Path -LiteralPath $src)) { throw "B06 requires B05's chk00010, which is absent: $src" }
        Copy-Item -LiteralPath $src -Destination $dir -Recurse
    }

    $common = @('input_fungi') + $case.args + @('amr.plot_int=-1')
    if ($case.id -ne 'B05_ckpt_write') { $common += 'amr.check_int=-1' }

    if ($case.ranks -eq 1) { $program = $exe;               $argv = $common }
    else                   { $program = $BmxTool.MpiExec;   $argv = @('-n', "$($case.ranks)", $exe) + $common }

    $log = Join-Path $dir 'stdout.log'
    Write-Host ("--- {0} : {1}" -f $case.id, $case.desc)
    $sw = [Diagnostics.Stopwatch]::StartNew()
    Push-Location $dir
    try {
        & $program @argv *>&1 | Out-File -FilePath $log -Encoding utf8
        $code = $LASTEXITCODE
    } finally { Pop-Location }
    $sw.Stop()

    $artifacts = @(Get-ChildItem -LiteralPath $dir -Recurse -File | ForEach-Object {
        [pscustomobject]@{
            path   = $_.FullName.Substring($dir.Length + 1).Replace('\','/')
            bytes  = $_.Length
            sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower()
        }
    })

    Write-Host ("    exit={0}  elapsed={1}s  artefacts={2}" -f $code, [math]::Round($sw.Elapsed.TotalSeconds,3), $artifacts.Count)

    $index += [pscustomobject]@{
        id             = $case.id
        description    = $case.desc
        ranks          = $case.ranks
        program        = $program
        arguments      = $argv
        exit_code      = $code
        elapsed_s      = [math]::Round($sw.Elapsed.TotalSeconds, 3)
        directory      = $dir
        artifacts      = $artifacts
    }
}

$runIndex = [pscustomobject]@{
    stage                = 'C03'
    generated_utc        = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    role                 = 'lean baseline; NOT an official P06 package and not P06 acceptance'
    source_worktree      = $SourceDir
    build_dir            = $BuildDir
    executable           = $exe
    executable_sha256    = $exeHash
    phosphorus_state     = 'feature-off reference: chem_species.p_growth_limit=0, mesh species A B C D F P (legacy 6-component order)'
    cases                = $index
}
$runIndex | ConvertTo-Json -Depth 6 | Out-File -FilePath (Join-Path $OutRoot 'RUN_INDEX.json') -Encoding utf8

$failed = @($index | Where-Object { $_.exit_code -ne 0 })
Write-Host ''
Write-Host ("cases: {0}  failed: {1}" -f $index.Count, $failed.Count)
if ($failed.Count -gt 0) {
    $failed | ForEach-Object { Write-Host ("  FAILED {0} exit={1}" -f $_.id, $_.exit_code) }
    throw 'baseline matrix had failing cases'
}
Write-Host "run index -> $(Join-Path $OutRoot 'RUN_INDEX.json')"
