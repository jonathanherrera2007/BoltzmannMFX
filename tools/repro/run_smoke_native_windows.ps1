# BMX RG-SW — minimal execution smoke test for the native Windows build.
#
# Runs, in order:
#   1. bmx.exe --describe        (build identity, no simulation)
#   2. bmx.exe <inputs> max_step=0   (initialise only)
#   3. bmx.exe <inputs> max_step=1   (one baseline step)
#
# Each run happens in its own scratch directory outside the Git worktree, so the
# source tree stays clean. Nothing here is a scientific result; this only proves
# the executable initialises and advances one step.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File run_smoke_native_windows.ps1 `
#              [-BuildDir <path>] [-RunRoot <path>]

[CmdletBinding()]
param(
    [string]$BuildDir,
    [string]$RunRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# Needed for $BmxTool.MpiExec in the two-rank stage.
. (Join-Path $scriptDir 'native_windows_env.ps1')
$sourceDir = (Resolve-Path (Join-Path $scriptDir '..\..')).Path
$rgswRoot  = Split-Path -Parent (Split-Path -Parent $sourceDir)

if (-not $BuildDir) { $BuildDir = Join-Path $rgswRoot 'build\c02-native-release' }
if (-not $RunRoot)  { $RunRoot  = Join-Path $rgswRoot 'runs\c02-smoke' }

$exe = Join-Path $BuildDir 'bmx.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw "executable not found: $exe`nRun build_native_windows.ps1 first." }

$caseDir = Join-Path $sourceDir 'exec\fungi'
foreach ($f in 'input_fungi', 'fungi_init_cfg.dat') {
    if (-not (Test-Path -LiteralPath (Join-Path $caseDir $f))) { throw "missing case input: $caseDir\$f" }
}

Write-Host "executable : $exe"
Write-Host "sha256     : $((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLower())"
Write-Host "run root   : $RunRoot"
Write-Host ''

function Invoke-Stage {
    param([string]$Name, [string]$Program, [string[]]$Arguments, [switch]$NeedsCase)

    $dir = Join-Path $RunRoot $Name
    if (Test-Path -LiteralPath $dir) { Remove-Item -LiteralPath $dir -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    if ($NeedsCase) {
        Copy-Item -LiteralPath (Join-Path $caseDir 'input_fungi')        -Destination $dir
        Copy-Item -LiteralPath (Join-Path $caseDir 'fungi_init_cfg.dat') -Destination $dir
    }

    $log = Join-Path $dir 'stdout.log'
    Write-Host "--- $Name : $Program $($Arguments -join ' ')"
    $sw = [Diagnostics.Stopwatch]::StartNew()
    Push-Location $dir
    try {
        # Out-File -Encoding utf8, not Tee-Object: Tee-Object writes UTF-16LE by
        # default on Windows PowerShell 5.1, which makes these logs unparseable
        # by the downstream analysis harnesses in C03/C05/C10/C14.
        & $Program @Arguments *>&1 | Out-File -FilePath $log -Encoding utf8
        $code = $LASTEXITCODE
    } finally { Pop-Location }
    $sw.Stop()

    Write-Host "    exit=$code  elapsed=$([math]::Round($sw.Elapsed.TotalSeconds,3))s  log=$log"
    return $code
}

$bmxArgs0 = @('input_fungi', 'bmx.max_step=0', 'amr.plot_int=-1', 'amr.check_int=-1')
$bmxArgs1 = @('input_fungi', 'bmx.max_step=1', 'amr.plot_int=-1', 'amr.check_int=-1')

$rc = @{}
$rc.describe = Invoke-Stage -Name 'describe'   -Program $exe -Arguments @('--describe')
$rc.step0    = Invoke-Stage -Name 'max_step_0' -Program $exe -Arguments $bmxArgs0 -NeedsCase
$rc.step1    = Invoke-Stage -Name 'max_step_1' -Program $exe -Arguments $bmxArgs1 -NeedsCase

# Two ranks under mpiexec. A one-rank run links MPI but never exercises a real
# send/recv, redistribution, or reduction, so it cannot show that the MPI build
# actually works. This is a launch check only -- it is NOT the rank/decomposition
# invariance study, which is predeclared and owned by C16.
$rc.mpi2 = Invoke-Stage -Name 'mpi_2rank' -Program $BmxTool.MpiExec `
                        -Arguments (@('-n', '2', $exe) + $bmxArgs1) -NeedsCase

Write-Host ''
Write-Host "describe          exit=$($rc.describe)"
Write-Host "max_step=0        exit=$($rc.step0)"
Write-Host "max_step=1        exit=$($rc.step1)"
Write-Host "max_step=1 2ranks exit=$($rc.mpi2)"

# --describe is informational; initialisation, the single step, and the two-rank
# launch are the gates.
if ($rc.step0 -ne 0 -or $rc.step1 -ne 0 -or $rc.mpi2 -ne 0) { throw 'smoke run FAILED' }
Write-Host 'smoke run OK'
