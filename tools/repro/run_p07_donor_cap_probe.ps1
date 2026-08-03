# BMX RG-SW -- C04 / P07 second-half donor-cap reachability probe.
#
# ############################################################################
# SUPERSEDED by tools/repro/run_p07_donor_cap_fixture.py. DO NOT cite this
# script's negative result as evidence about the code.
#
# This probe concluded "NOT REACHED under any k1 tested". That conclusion was
# an artefact of its DETECTOR, not a property of the model. It watched for a
# sign flip in the particle-side transfer, and a sign flip can only occur when
# the BASELINE cap fires -- only the baseline assignment
# dA2 = -fA_tmp*fluid_vol reverses the transfer direction. A repaired-side-only
# activation is invisible to it.
#
# It also never removed two confounds that suppressed the exchange entirely:
# the particle sits at z = 0.0752, just above fluid.surface_location = 0.075
# where the initial fluid A is zero, and rA = -k2*cA + kr2*cB*cC drains A far
# faster than the exchange moves it.
#
# With a fluid-side observable (bmx.print_sums) and those confounds removed,
# the cap demonstrably fires and the capped transfer equals the available
# amount to machine precision. Retained only as the record of a detector that
# could not answer the question.
# ############################################################################
#
# WHAT THIS TESTS
# ---------------
# CDEF-01 / CDEF-02 are the second-half fluid donor cap, bmx_chem_K.H:2188
# (species A) and :2220 (species C). The patch changes
#
#     dA2 = -fA_tmp*fluid_vol ;  dfA = -fA_tmp      (baseline: A is DESTROYED --
#                                                    the fluid is zeroed and the
#                                                    particle is debited too)
#     dA2 =  fA_tmp*fluid_vol ;  dfA = dA2/fluid_vol (repaired: the particle is
#                                                    credited exactly the amount
#                                                    the fluid had)
#
# So if the branch executes, the sign of the amount moved flips between trees.
# realIdx::first_data + 2*NUM_CHEM_COMPONENTS accumulates -(dA1+dA2) per
# species, so the particle ASCII dump records that amount directly. A sign flip
# there is an unambiguous, directly observed activation of the branch.
#
# WHY IT IS A PROBE AND NOT A PASSING FIXTURE
# -------------------------------------------
# No k1 tested activates the branch. Two mechanisms suppress it, both read off
# the source rather than guessed:
#
#   1. The FIRST-half cap at :1686 is already correct in the canonical baseline
#      -- the patch does not touch it. Under a large k1 it fires first, sets
#      fA_tmp = 0, and the second half then computes
#      dA2 = 0.5*dtp*area*(k1*0 - kr1*cA) < 0, which returns A to the fluid and
#      raises fA_tmp. The second-half cap cannot fire behind it.
#
#   2. The exchange is a two-way rate, 0.5*dtp*area*(k1*fA_tmp - kr1*cA). As k1
#      rises, cA equilibrates upward and the NET transfer self-limits instead of
#      overshooting the fluid content. Raising k1 does not drive the requested
#      decrement past the available amount.
#
# The analytic threshold from the source is
#   alpha = 0.5*dtp*area*k1/fluid_vol > 1, with fluid_vol = grid_vol/npart
#         (:1438), dtp = fixed_dt/substeps = 0.0625, area = 5.105e-6 cm^2,
#         level-1 cell volume ~2.44e-7 cm^3  ->  k1 > ~1.5
# so the sweep brackets that value closely and then extends far past it.
#
# This script exists so the negative result is REPRODUCIBLE and reviewable
# rather than an undocumented conclusion. It must be re-run if the exchange
# law, the substep count, or the cell size changes.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File run_p07_donor_cap_probe.ps1

[CmdletBinding()]
param(
    [string]$BaselineExe,
    [string]$RepairedExe,
    [string]$CaseDir,
    [string]$OutRoot,
    [double[]]$K1Values = @(0.8, 1.2, 1.5, 1.8, 2.2, 3.0, 5.0, 10.0, 100.0, 1000.0),
    [int]$MaxStep = 8,
    [int]$TimeoutSeconds = 300
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$product   = (Resolve-Path (Join-Path $scriptDir '..\..')).Path
$rgswRoot  = Split-Path -Parent (Split-Path -Parent $product)

if (-not $BaselineExe) { $BaselineExe = Join-Path $rgswRoot 'build\c03-baseline-release\bmx.exe' }
if (-not $RepairedExe) { $RepairedExe = Join-Path $rgswRoot 'build\c04-p07-release\bmx.exe' }
if (-not $CaseDir)     { $CaseDir     = Join-Path $product  'exec\fungi' }
if (-not $OutRoot)     { $OutRoot     = Join-Path $rgswRoot 'runs\c04-p07-donor-cap' }

foreach ($e in @($BaselineExe, $RepairedExe)) {
    if (-not (Test-Path -LiteralPath $e)) { throw "executable not found: $e" }
}
if (Test-Path -LiteralPath $OutRoot) { Remove-Item -LiteralPath $OutRoot -Recurse -Force }
New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null

function Invoke-One {
    param([string]$Exe, [string]$Dir, [double]$K1)
    New-Item -ItemType Directory -Force -Path $Dir | Out-Null
    Copy-Item -LiteralPath (Join-Path $CaseDir 'input_fungi')        -Destination $Dir
    Copy-Item -LiteralPath (Join-Path $CaseDir 'fungi_init_cfg.dat') -Destination $Dir
    $argv = @('input_fungi', "bmx.max_step=$MaxStep", 'amr.plot_int=-1', 'amr.check_int=-1',
              "amr.par_ascii_int=$MaxStep", 'amr.par_ascii_file=par',
              ("chem_species.k1={0}" -f $K1))
    $log = Join-Path $Dir 'stdout.log'
    $p = Start-Process -FilePath $Exe -ArgumentList ($argv -join ' ') -WorkingDirectory $Dir `
                       -RedirectStandardOutput $log -RedirectStandardError (Join-Path $Dir 'stderr.log') `
                       -NoNewWindow -PassThru
    $null = $p.Handle
    if ($p.WaitForExit($TimeoutSeconds * 1000)) { $code = $p.ExitCode }
    else { try { $p.Kill() } catch { }; $p.WaitForExit(10000) | Out-Null; $code = 'TIMEOUT' }
    return $code
}

Write-Host "second-half donor-cap reachability probe (CDEF-01 / CDEF-02)"
Write-Host "sweeping chem_species.k1; a SIGN FLIP in the recorded A amount means the branch fired"
Write-Host ''

$rows = @()
foreach ($k1 in $K1Values) {
    $tag = "k1_$($k1.ToString('G', [Globalization.CultureInfo]::InvariantCulture) -replace '[.+]','_')"
    $bd = Join-Path $OutRoot "$tag\baseline"
    $rd = Join-Path $OutRoot "$tag\repaired"
    $bx = Invoke-One -Exe $BaselineExe -Dir $bd -K1 $k1
    $rx = Invoke-One -Exe $RepairedExe -Dir $rd -K1 $k1

    $json = Join-Path $OutRoot "$tag\GEOMETRY.json"
    & python (Join-Path $scriptDir 'analyze_p07_geometry.py') `
        --compare $bd $rd --radius-max 2.5e-4 --length-max 35.0e-4 --json-out $json | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "analyzer failed for k1=$k1" }
    $g = Get-Content -LiteralPath $json -Raw | ConvertFrom-Json

    # First particle's recorded A and C amounts, both trees.
    $bk = ($g.baseline.final_state.PSObject.Properties | Sort-Object Name | Select-Object -First 1)
    $rk = ($g.repaired.final_state.PSObject.Properties | Sort-Object Name | Select-Object -First 1)
    $bA = $bk.Value.transferred_amount.A ; $rA = $rk.Value.transferred_amount.A
    $bC = $bk.Value.transferred_amount.C ; $rC = $rk.Value.transferred_amount.C
    $flipA = ($bA * $rA) -lt 0
    $flipC = ($bC * $rC) -lt 0

    Write-Host ("  k1={0,-8} A base={1,13:e4} rep={2,13:e4} flip={3,-5}  C base={4,13:e4} rep={5,13:e4} flip={6}" `
                -f $k1, $bA, $rA, $flipA, $bC, $rC, $flipC)

    $rows += [pscustomobject]@{
        k1 = $k1; baseline_exit = $bx; repaired_exit = $rx
        baseline_amount_A = $bA; repaired_amount_A = $rA; sign_flip_A = $flipA
        baseline_amount_C = $bC; repaired_amount_C = $rC; sign_flip_C = $flipC
        cap_activated = ($flipA -or $flipC)
        geometry_json = $json
    }
}

$activated = @($rows | Where-Object { $_.cap_activated })
$out = [pscustomobject]@{
    superseded_by = 'tools/repro/run_p07_donor_cap_fixture.py'
    superseded_reason = ('the sign-flip detector can only see a BASELINE-side cap activation, so a ' +
                         'repaired-side-only firing is invisible to it; this negative result is a ' +
                         'detector artefact and is NOT evidence about the model')
    generated_utc = (Get-Date).ToUniversalTime().ToString('o')
    purpose       = 'reachability probe for the second-half fluid donor cap (CDEF-01/CDEF-02)'
    observable    = 'sign of realIdx::first_data + 2*NUM_CHEM_COMPONENTS (accumulated -(dA1+dA2)) in the particle ASCII dump'
    analytic_threshold_k1 = 1.5
    suppression_mechanisms = @(
        'first-half cap at bmx_chem_K.H:1686 is already correct in the baseline and fires first, zeroing fA_tmp',
        'exchange is two-way (k1*fA - kr1*cA), so cA equilibrates and the net request self-limits instead of overshooting'
    )
    k1_values_tested = $K1Values
    activations      = $activated.Count
    conclusion       = $(if ($activated.Count -gt 0) { 'REACHED' } else { 'NOT REACHED under any k1 tested' })
    rows             = $rows
}
$out | ConvertTo-Json -Depth 8 | Out-File -FilePath (Join-Path $OutRoot 'DONOR_CAP_PROBE.json') -Encoding utf8

Write-Host ''
Write-Host ("activations : {0} / {1}" -f $activated.Count, $rows.Count)
Write-Host ("conclusion  : {0}" -f $out.conclusion)
Write-Host ("index       : {0}" -f (Join-Path $OutRoot 'DONOR_CAP_PROBE.json'))
