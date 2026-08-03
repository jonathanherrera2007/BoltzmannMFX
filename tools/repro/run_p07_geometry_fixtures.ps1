# BMX RG-SW -- C04 / P07 geometry-observable fixtures.  Resolves B-C04-01.
#
# WHY THIS EXISTS
# ---------------
# The first C04 fixture matrix could not distinguish which growth branch ran.
# It compared normalized stdout logs and reported "lines differing" and "max
# relative difference". Both are STRUCTURAL statistics: a 20-step run produces
# about the same number of differing MLMG lines no matter which geometry branch
# executed. So F3 and F4 could not be separated from the stock reference, and
# CDEF-04 / CDEF-05 stayed unproven.
#
# A second, worse problem was found while building this: the old F3 fixture
# (`max_seg_radius=1.0e-6`) selects the SAME branch as stock parameters.
# The stock case has initial radius 2.5e-4 and `max_seg_radius = 2.5e-4`, so
# `radius < radius_max` is already FALSE at t=0, and the tip path is
# length-only from the first step. Lowering the maximum further changes
# nothing. F3 was a no-op relative to its own reference -- not a resolution
# problem. Recorded as D-C04-02.
#
# WHAT THIS DOES INSTEAD
# ----------------------
# Enables `amr.par_ascii_int`, which dumps every particle real/int field per
# step at precision 15. That is pure output: fixture G0 proves the trajectory
# is unchanged with it on. So the kernel is observed at the exact reviewed
# candidate bytes -- no instrumentation, candidate hash preserved.
#
# Each fixture selects one growth branch by construction, and
# analyze_p07_geometry.py independently (a) predicts the branch from the
# source's own predicates and (b) classifies what actually changed. The two
# must agree.
#
# Every override is an ENGINEERING TEST VALUE chosen to force a code branch.
# None is biological, none is calibrated, none may be promoted to scientific
# evidence.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File run_p07_geometry_fixtures.ps1

[CmdletBinding()]
param(
    [string]$BaselineExe,
    [string]$RepairedExe,
    [string]$CaseDir,
    [string]$OutRoot,
    [int]$TimeoutSeconds = 600
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$product   = (Resolve-Path (Join-Path $scriptDir '..\..')).Path
$rgswRoot  = Split-Path -Parent (Split-Path -Parent $product)

if (-not $BaselineExe) { $BaselineExe = Join-Path $rgswRoot 'build\c03-baseline-release\bmx.exe' }
if (-not $RepairedExe) { $RepairedExe = Join-Path $rgswRoot 'build\c04-p07-release\bmx.exe' }
if (-not $CaseDir)     { $CaseDir     = Join-Path $product  'exec\fungi' }
if (-not $OutRoot)     { $OutRoot     = Join-Path $rgswRoot 'runs\c04-p07-geometry' }

foreach ($e in @($BaselineExe, $RepairedExe)) {
    if (-not (Test-Path -LiteralPath $e)) { throw "executable not found: $e" }
}

$baseHash = (Get-FileHash -LiteralPath $BaselineExe -Algorithm SHA256).Hash.ToLower()
$repHash  = (Get-FileHash -LiteralPath $RepairedExe -Algorithm SHA256).Hash.ToLower()
Write-Host "baseline exe : $BaselineExe"
Write-Host "  sha256     : $baseHash"
Write-Host "repaired exe : $RepairedExe"
Write-Host "  sha256     : $repHash"
Write-Host ''

if (Test-Path -LiteralPath $OutRoot) { Remove-Item -LiteralPath $OutRoot -Recurse -Force }
New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null

# Stock values from exec/fungi/input_fungi, needed by the analyzer to evaluate
# the branch predicates. A fixture that overrides one must declare it here too.
$STOCK_RMAX = 2.5e-4
$STOCK_LMAX = 35.0e-4

# branch = the bmx_chem_K.H branch this fixture is constructed to select
$fixtures = @(
    # ---- CDEF-04: the two tip paths that never refresh the stored area -----
    @{ id='G1_tip_length_only'; branch='TIP_LENGTH_ONLY'; defect='CDEF-04'
       desc='stock parameters. radius(2.5e-4) >= max_seg_radius(2.5e-4) at t=0, so :2044 and :2064 are both false and the tip takes the length-only path :2072'
       args=@('bmx.max_step=40'); rmax=$STOCK_RMAX; lmax=$STOCK_LMAX },

    @{ id='G2_tip_radius_only'; branch='TIP_RADIUS_ONLY'; defect='CDEF-04'
       desc='raise max radius above r and drop max length below L: :2044 false (L not < Lmax), :2064 true (r < rmax) -> radius-only path'
       args=@('bmx.max_step=40','chem_species.max_seg_radius=1.0e-3','chem_species.max_seg_length=1.0e-3')
       rmax=1.0e-3; lmax=1.0e-3 },

    # ---- Contrast: the tip path that DOES refresh the stored area ---------
    @{ id='G3_tip_proportional'; branch='TIP_PROPORTIONAL'; defect='none (contrast)'
       desc='raise both maxima so :2044 is true -> proportional path, which DOES write realIdx::area. Distinguishes "area is stale" from "area never changes".'
       args=@('bmx.max_step=40','chem_species.max_seg_radius=1.0e-3','chem_species.max_seg_length=1.0e-2')
       rmax=1.0e-3; lmax=1.0e-2 },

    # ---- CDEF-05: non-tip max-radius growth rejection ----------------------
    #
    # A non-tip segment requires at least two splits: the first split makes
    # both daughters TIP (:543,:560); only a later split assigns SECOND_1 /
    # SECOND_2 and then INTERIOR. Natural growth never gets there -- rV is
    # B-limited at roughly 2.5e-7 relative volume per substep, so a second
    # split would take millions of substeps.
    #
    # checkSplit (:41-70) triggers on `radius >= max_rad && c_length >=
    # max_len`, so lowering max_seg_length cascades splits and builds a chain
    # in ~3 steps. It does NOT change the growth predicates being tested:
    # radius still equals max_seg_radius, so every non-tip segment takes the
    # rejection path :2098.
    @{ id='G4_nontip_rejected'; branch='NONTIP_REJECTED'; defect='CDEF-05'
       desc='cascade splits into a multi-segment chain; non-tip segments have radius >= max_seg_radius so :2084 is false and growth is rejected at :2098'
       args=@('bmx.max_step=30','chem_species.max_seg_length=6.0e-4','chem_species.seg_split_length=3.0e-4')
       rmax=$STOCK_RMAX; lmax=6.0e-4 },

    # ---- Contrast: the non-tip path that DOES grow ------------------------
    #
    # EXPECTED NOT REACHED, and the reason is structural rather than a fixture
    # weakness. Reaching :2084 needs a non-tip segment with radius < max_rad.
    # But a non-tip segment can only be produced by a split, and checkSplit
    # (:46) requires `radius >= max_rad` before it will split anything. The
    # split paths change c_length, never radius. So every non-tip segment that
    # can exist carries radius >= max_rad and necessarily takes the rejection
    # path :2098 instead.
    #
    # Raising max_seg_radius to admit :2084 simultaneously suppresses the
    # splitting that would create a non-tip segment at all -- which is exactly
    # what this fixture demonstrates: one particle, no chain, no non-tip
    # segment. From a single-segment initial condition and a fixed max_rad,
    # :2084 is unreachable. Recorded as D-C04-04. It is NOT a P07 defect
    # mapping and no C04 mandatory row depends on it.
    @{ id='G5_nontip_radial'; branch='NONTIP_RADIAL'; defect='none (contrast, expected unreachable)'
       desc='raises max radius so :2084 could fire, but that same predicate gates checkSplit, so no chain forms and no non-tip segment exists. Demonstrates :2084 is unreachable from this initial condition.'
       args=@('bmx.max_step=30','chem_species.max_seg_length=6.0e-4','chem_species.seg_split_length=3.0e-4','chem_species.max_seg_radius=1.0e-3')
       rmax=1.0e-3; lmax=6.0e-4; expect_unreachable=$true },

    # ---- No-trigger control, stock initial condition -----------------------
    # kv = 0 makes rV = kv*cB*orig_cell_vol identically zero, so geometry never
    # changes. The C04 report asserted the repair is therefore EXACTLY inert,
    # on the grounds that the initial config is self-consistent. That claim is
    # false, and this fixture is what shows it:
    #
    #   fungi_init_cfg.dat stores area = 5.105e-6 (four significant figures)
    #   2*pi*r*(r+L) with r=2.5e-4, L=3.0e-3 = 5.105088062083415e-6
    #   relative mismatch                    = 1.725e-5
    #
    # The repair recomputes carbon_exchange_area from live radius/length
    # instead of reading the stored field, so it corrects that rounding on the
    # very first step -- even with growth switched off. The original N1 control
    # was declared "bit-identical" from normalized stdout logs, an observable
    # too coarse to resolve a 1.7e-5 concentration difference. Recorded as
    # D-C04-03.
    @{ id='G6_no_growth_stock_init'; branch='NO_GROWTH'; defect='none (control)'
       desc='kv=0 with the STOCK init file. Geometry is inert, but the repair still differs by ~1.7e-5 because the stored area is rounded to 4 s.f.'
       args=@('bmx.max_step=20','chem_species.kv=0.0'); rmax=$STOCK_RMAX; lmax=$STOCK_LMAX
       expect_identical=$false },

    # ---- No-trigger control, self-consistent initial condition ------------
    # Same fixture with the stored area written at full precision. If the
    # repair is genuinely confined to the reviewed predicates, this must be
    # bit-identical -- and that is what isolates the 1.7e-5 above as an
    # artefact of the input file rather than the patch reaching further than
    # reviewed. Only the area field is corrected: it is the one field the
    # repair recomputes, so correcting anything else would blur the attribution.
    @{ id='G7_no_growth_exact_init'; branch='NO_GROWTH'; defect='none (control)'
       desc='kv=0 with a self-consistent init file (area written at full precision). The repair must now be EXACTLY inert.'
       args=@('bmx.max_step=20','chem_species.kv=0.0'); rmax=$STOCK_RMAX; lmax=$STOCK_LMAX
       initcfg='fixtures\fungi_init_cfg_selfconsistent.dat'; expect_identical=$true }
)

function Invoke-Tree {
    # The parameter is deliberately NOT named $Args: that collides with
    # PowerShell's automatic $args and silently drops every model override.
    param([string]$Exe, [string]$Dir, [string[]]$ModelArgs, [int]$Ranks = 1,
          [int]$TimeoutSeconds = 600, [switch]$NoAscii, [string]$InitCfg)
    New-Item -ItemType Directory -Force -Path $Dir | Out-Null
    Copy-Item -LiteralPath (Join-Path $CaseDir 'input_fungi') -Destination $Dir
    # particles.input_file is always "fungi_init_cfg.dat"; an alternate initial
    # condition is supplied by copying it to that name, not by editing inputs.
    $src = if ($InitCfg) { Join-Path $scriptDir $InitCfg }
           else          { Join-Path $CaseDir 'fungi_init_cfg.dat' }
    if (-not (Test-Path -LiteralPath $src)) { throw "init config not found: $src" }
    Copy-Item -LiteralPath $src -Destination (Join-Path $Dir 'fungi_init_cfg.dat')

    $io = if ($NoAscii) { @('amr.par_ascii_int=-1') }
          else          { @('amr.par_ascii_int=1','amr.par_ascii_file=par') }
    $argv = @('input_fungi') + $ModelArgs + @('amr.plot_int=-1','amr.check_int=-1') + $io

    $log = Join-Path $Dir 'stdout.log'
    $err = Join-Path $Dir 'stderr.log'
    # -ArgumentList with an ARRAY mangles arguments (every name=value override
    # is dropped); pass one pre-joined string. And the timed WaitForExit
    # overload returns $false immediately unless .Handle is touched first.
    $program = $Exe
    if ($Ranks -gt 1) { $program = $BmxTool2.MpiExec; $argv = @('-n', "$Ranks", $Exe) + $argv }
    $p = Start-Process -FilePath $program -ArgumentList ($argv -join ' ') -WorkingDirectory $Dir `
                       -RedirectStandardOutput $log -RedirectStandardError $err `
                       -NoNewWindow -PassThru
    $null = $p.Handle
    if ($p.WaitForExit($TimeoutSeconds * 1000)) { $code = $p.ExitCode }
    else {
        try { $p.Kill() } catch { }
        $p.WaitForExit(10000) | Out-Null
        Write-Host ("    TIMEOUT after {0}s -- killed" -f $TimeoutSeconds)
        $code = 'TIMEOUT'
    }

    # Do not trust that the overrides arrived -- prove it from the output.
    $requested = ($ModelArgs | Where-Object { $_ -like 'bmx.max_step=*' } |
                  ForEach-Object { [int]($_ -split '=')[1] } | Select-Object -First 1)
    if ($null -ne $requested -and (Test-Path -LiteralPath $log)) {
        $lastStep = Select-String -LiteralPath $log -Pattern '^\s*Step (\d+):' |
                    ForEach-Object { [int]$_.Matches[0].Groups[1].Value } |
                    Measure-Object -Maximum | Select-Object -ExpandProperty Maximum
        if ($null -ne $lastStep -and $lastStep -gt $requested) {
            throw ("override was dropped: requested bmx.max_step=$requested but the run reached step $lastStep. " +
                   "Fix the harness before trusting any fixture result.")
        }
    }
    if (-not $NoAscii) {
        $dumps = @(Get-ChildItem -LiteralPath $Dir -Filter 'par?????' -ErrorAction SilentlyContinue)
        if ($dumps.Count -lt 2) {
            throw ("no particle dumps in $Dir -- amr.par_ascii_int did not take effect. " +
                   "The geometry observable is the entire point of this fixture; refusing to report a result.")
        }
    }
    return @{ exit = $code; log = $log; dir = $Dir }
}

. (Join-Path $scriptDir 'native_windows_env.ps1')
$BmxTool2 = $BmxTool

# ---------------------------------------------------------------------------
# G0 -- observation neutrality.
# Everything below depends on particle ASCII output not perturbing the run.
# Prove that first, on the repaired image, before any fixture is believed.
# ---------------------------------------------------------------------------
Write-Host '--- G0_ascii_neutrality  [does observing change the result?]'
$g0 = Join-Path $OutRoot 'G0_ascii_neutrality'
$on  = Invoke-Tree -Exe $RepairedExe -Dir (Join-Path $g0 'ascii_on')  -ModelArgs @('bmx.max_step=40') -TimeoutSeconds $TimeoutSeconds
$off = Invoke-Tree -Exe $RepairedExe -Dir (Join-Path $g0 'ascii_off') -ModelArgs @('bmx.max_step=40') -TimeoutSeconds $TimeoutSeconds -NoAscii

# Wall-clock timing lines are nondeterministic by construction; everything else
# must match exactly.
$strip = { param($f) (Get-Content -LiteralPath $f) | Where-Object { $_ -notmatch 'Time|time|seconds|memory|Memory' } }
$onN  = & $strip $on.log
$offN = & $strip $off.log
$neutral = -not (Compare-Object $onN $offN)
Write-Host ("    non-timing lines compared : {0}" -f $onN.Count)
Write-Host ("    NEUTRALITY                : {0}" -f $(if ($neutral) {'PASS (identical)'} else {'FAIL (differs)'}))
if (-not $neutral) {
    throw "particle ASCII output changed the trajectory. Every geometry fixture below would be measuring the observer, not the model. Stopping."
}
Write-Host ''

$results = @()
foreach ($f in $fixtures) {
    $fdir = Join-Path $OutRoot $f.id
    Write-Host ("--- {0}  [target branch {1}]  defect {2}" -f $f.id, $f.branch, $f.defect)
    Write-Host ("    {0}" -f $f.desc)

    $initCfg = if ($f.ContainsKey('initcfg')) { $f.initcfg } else { '' }
    $b = Invoke-Tree -Exe $BaselineExe -Dir (Join-Path $fdir 'baseline') -ModelArgs $f.args -TimeoutSeconds $TimeoutSeconds -InitCfg $initCfg
    $r = Invoke-Tree -Exe $RepairedExe -Dir (Join-Path $fdir 'repaired') -ModelArgs $f.args -TimeoutSeconds $TimeoutSeconds -InitCfg $initCfg
    Write-Host ("    baseline exit={0}  repaired exit={1}" -f $b.exit, $r.exit)

    $json = Join-Path $fdir 'GEOMETRY.json'
    & python (Join-Path $scriptDir 'analyze_p07_geometry.py') `
        --compare $b.dir $r.dir --radius-max $f.rmax --length-max $f.lmax --json-out $json | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "analyze_p07_geometry.py failed for $($f.id)" }

    $g = Get-Content -LiteralPath $json -Raw | ConvertFrom-Json
    $obs = $g.repaired.observed_branch_counts
    $pre = $g.repaired.predicted_branch_counts
    $hit = $obs.PSObject.Properties.Name -contains $f.branch
    Write-Host ("    predicted : {0}" -f (($pre.PSObject.Properties | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join ' '))
    Write-Host ("    observed  : {0}" -f (($obs.PSObject.Properties | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join ' '))
    Write-Host ("    target branch reached : {0}" -f $(if ($hit) {'YES'} else {'NO'}))

    # Baseline-vs-repaired difference. For a control this must be empty; the
    # exact-init control G7 is the one that isolates the repair from the
    # rounding in the stock input file.
    $identical = $g.summary.trees_identical
    $nDiff     = $g.summary.particles_differing
    Write-Host ("    baseline vs repaired  : {0}" -f $(if ($identical) {'IDENTICAL'} else {"$nDiff particle(s) differ, max_rel=$('{0:e3}' -f $g.summary.max_rel)"}))

    $verdict = 'INFO'
    if ($f.ContainsKey('expect_identical')) {
        $verdict = if ($identical -eq $f.expect_identical) { 'PASS' } else { 'FAIL' }
        Write-Host ("    control expectation   : expect_identical=$($f.expect_identical) -> $verdict")
    } elseif ($f.ContainsKey('expect_unreachable')) {
        # Predeclared before the run: this branch is argued unreachable. If it
        # DOES fire, the argument is wrong and that must surface as a failure,
        # not be quietly absorbed.
        $verdict = if ($hit) { 'FAIL_UNEXPECTEDLY_REACHED' } else { 'PASS_UNREACHABLE_AS_PREDICTED' }
        Write-Host ("    unreachability        : $verdict")
    } elseif ($hit) { $verdict = 'PASS' } else { $verdict = 'NOT_REACHED' }

    $results += [pscustomobject]@{
        id                = $f.id
        target_branch     = $f.branch
        defect            = $f.defect
        description       = $f.desc
        arguments         = $f.args
        init_cfg          = $(if ($initCfg) { $initCfg } else { 'exec/fungi/fungi_init_cfg.dat' })
        radius_max        = $f.rmax
        length_max        = $f.lmax
        baseline_exit     = $b.exit
        repaired_exit     = $r.exit
        baseline_dir      = $b.dir
        repaired_dir      = $r.dir
        geometry_json     = $json
        branch_reached    = $hit
        trees_identical   = $identical
        particles_differing = $nDiff
        fields_differing  = $g.summary.fields_differing
        max_rel           = $g.summary.max_rel
        verdict           = $verdict
    }
    Write-Host ''
}

$index = [pscustomobject]@{
    generated_utc        = (Get-Date).ToUniversalTime().ToString('o')
    baseline_exe         = $BaselineExe
    baseline_exe_sha256  = $baseHash
    repaired_exe         = $RepairedExe
    repaired_exe_sha256  = $repHash
    case_dir             = $CaseDir
    ascii_neutrality     = $(if ($neutral) {'PASS'} else {'FAIL'})
    fixtures             = $results
}
$index | ConvertTo-Json -Depth 8 | Out-File -FilePath (Join-Path $OutRoot 'GEOMETRY_INDEX.json') -Encoding utf8

Write-Host ('=' * 70)
foreach ($r in $results) { Write-Host ("{0,-28} {1,-30} {2}" -f $r.id, $r.target_branch, $r.verdict) }
Write-Host ('=' * 70)
$bad = @($results | Where-Object { $_.verdict -like 'FAIL*' -or $_.verdict -eq 'NOT_REACHED' })
Write-Host ("fixtures run   : {0}" -f $results.Count)
Write-Host ("failing        : {0}" -f $bad.Count)
Write-Host ("index          : {0}" -f (Join-Path $OutRoot 'GEOMETRY_INDEX.json'))
if ($bad.Count -gt 0) { Write-Host ("NOT ALL FIXTURES MET THEIR PREDECLARED EXPECTATION") }
