# BMX RG-SW — C04 P07 runtime fixtures.
#
# Runs the SAME inputs against the untouched baseline image and the P07-repaired
# image, and compares normalized output. This is a DIFFERENTIAL fixture design,
# chosen deliberately:
#
#   * The C03 baseline showed the default `fungi` case never reaches the
#     donor-exhaustion branches, so a single-tree run proves nothing about them.
#   * The patched branches cannot be observed directly without instrumenting the
#     source, which would change the candidate hash away from the reviewed bytes.
#
# So reachability is established by DIFFERENCE: if baseline and repaired outputs
# diverge for a fixture, the patched code path was executed. If they are
# identical, it was not -- and that is reported as NOT REACHED rather than
# quietly counted as a pass.
#
# Every parameter override here is an ENGINEERING TEST VALUE chosen to force a
# specific code branch. None is a biological value, none is calibrated, and none
# may be promoted to scientific evidence.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File run_p07_fixtures.ps1

[CmdletBinding()]
param(
    [string]$BaselineExe,
    [string]$RepairedExe,
    [string]$CaseDir,
    [string]$OutRoot,
    [int]$TimeoutSeconds = 180
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$product   = (Resolve-Path (Join-Path $scriptDir '..\..')).Path
$rgswRoot  = Split-Path -Parent (Split-Path -Parent $product)

if (-not $BaselineExe) { $BaselineExe = Join-Path $rgswRoot 'build\c03-baseline-release\bmx.exe' }
if (-not $RepairedExe) { $RepairedExe = Join-Path $rgswRoot 'build\c04-p07-release\bmx.exe' }
if (-not $CaseDir)     { $CaseDir     = Join-Path $product  'exec\fungi' }
if (-not $OutRoot)     { $OutRoot     = Join-Path $rgswRoot 'runs\c04-p07-fixtures' }

foreach ($e in @($BaselineExe, $RepairedExe)) {
    if (-not (Test-Path -LiteralPath $e)) { throw "executable not found: $e" }
}

Write-Host "baseline exe : $BaselineExe"
Write-Host "  sha256     : $((Get-FileHash -LiteralPath $BaselineExe -Algorithm SHA256).Hash.ToLower())"
Write-Host "repaired exe : $RepairedExe"
Write-Host "  sha256     : $((Get-FileHash -LiteralPath $RepairedExe -Algorithm SHA256).Hash.ToLower())"
Write-Host ''

if (Test-Path -LiteralPath $OutRoot) { Remove-Item -LiteralPath $OutRoot -Recurse -Force }
New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null

# hook  = the P07 validation hook this fixture targets
# expect= 'DIFFER' if the repair should change behaviour, 'SAME' for controls
$fixtures = @(
    # k1/k3 = 100 is DERIVED, not guessed. The second-half fluid cap fires when
    # the requested fluid decrement exceeds the fluid content:
    #   0.5 * dtp * area * k / fluid_vol > 1
    # with dtp = fixed_dt/substeps = 0.25/4 = 0.0625, initial exchange area
    # 5.105e-6 cm^2 (fungi_init_cfg.dat), and a level-1 cell volume of about
    # 2.44e-7 cm^3, this is k > ~1.5. k = 100 overshoots by ~65x: comfortably
    # into the branch while staying numerically tractable.
    # An earlier attempt used 1e6 (~650,000x overshoot) and stalled the implicit
    # diffusion solve -- the run had to be killed. Recorded in the stage report.
    @{ id='F1_donor_cap_A'; hook='AT_P07_DONOR_CAP_A'; expect='DIFFER'
       desc='force second-half A donor exhaustion via k1=100 (derived: branch fires above k~1.5)'
       args=@('bmx.max_step=20','chem_species.k1=100.0') },

    @{ id='F2_donor_cap_C'; hook='AT_P07_DONOR_CAP_C'; expect='DIFFER'
       desc='force second-half C donor exhaustion via k3=100 (same derivation)'
       args=@('bmx.max_step=20','chem_species.k3=100.0') },

    @{ id='F3_area_refresh_tip'; hook='AT_P07_LOCAL_AREA_REFRESH / AT_P07_STORED_AREA_BRANCHES'; expect='DIFFER'
       desc='tiny max radius forces tip radius-only/length-only growth branches, which never refresh stored area'
       args=@('bmx.max_step=20','chem_species.max_seg_radius=1.0e-6') },

    @{ id='F4_rejected_growth'; hook='AT_P07_REJECTED_GROWTH_CARBON_ROLLBACK'; expect='DIFFER'
       desc='tiny max radius plus a longer run to reach non-tip max-radius growth rejection'
       args=@('bmx.max_step=200','chem_species.max_seg_radius=1.0e-6') },

    # TRUE no-trigger controls.
    #
    # An earlier version used stock parameters as the "no-trigger" control and
    # all three changed, which read like "the repair is not confined to the
    # reviewed predicates". That was a fixture-design error, not a defect:
    # CDEF-03/CDEF-04 are stored-area-refresh defects, and the tip geometry
    # path runs on essentially every growth step, so stock parameters trigger a
    # reviewed predicate constantly.
    #
    # kv = 0 makes rV = kv*cB*orig_cell_vol identically zero, so dV = 0, the
    # geometry never changes, and the refreshed carbon_exchange_area equals the
    # stored area (the initial configuration is self-consistent:
    # 2*pi*r*(r+L) with r=2.5e-4, L=3.0e-3 gives exactly the stored 5.105e-6).
    # The repair must therefore be EXACTLY inert here. This is the real
    # AT_P07_NO_TRIGGER_REGRESSION check.
    @{ id='N1_no_growth'; hook='AT_P07_NO_TRIGGER_REGRESSION'; expect='SAME'
       desc='true control: kv=0 so no volume growth, geometry never changes, repair must be inert'
       args=@('bmx.max_step=20','chem_species.kv=0.0') },

    @{ id='N2_init_only'; hook='AT_P07_NO_TRIGGER_REGRESSION'; expect='SAME'
       desc='true control: initialisation only, no chemistry update at all'
       args=@('bmx.max_step=0') },

    @{ id='N3_no_growth_2rank'; hook='AT_P07_NO_TRIGGER_REGRESSION'; expect='SAME'
       desc='true control: kv=0 under 2 MPI ranks'
       args=@('bmx.max_step=20','chem_species.kv=0.0'); ranks=2 },

    # Blast-radius references, NOT controls. Stock parameters DO trigger the
    # area-refresh predicate, so these are expected to differ; they quantify how
    # far the repair reaches under default settings and provide the floor that
    # the targeted fixtures above must exceed.
    @{ id='S1_stock_short'; hook='blast-radius reference'; expect='DIFFER'
       desc='stock parameters, 20 steps: area refresh applies on every tip growth step'
       args=@('bmx.max_step=20') },

    @{ id='S2_stock_long'; hook='blast-radius reference'; expect='DIFFER'
       desc='stock parameters, 200 steps'
       args=@('bmx.max_step=200') }
)

function Invoke-Tree {
    # NOTE: the parameter is deliberately NOT named $Args. $Args collides with
    # PowerShell's automatic $args variable, and the collision silently drops the
    # caller's values: every model override (bmx.max_step, chem_species.k1, ...)
    # vanished, so runs used the inputs-file default of 200000 steps and hit the
    # wall clock. Observed: a 20-step fixture reached step 4174.
    param([string]$Exe, [string]$Dir, [string[]]$ModelArgs, [int]$Ranks, [int]$TimeoutSeconds = 180)
    New-Item -ItemType Directory -Force -Path $Dir | Out-Null
    Copy-Item -LiteralPath (Join-Path $CaseDir 'input_fungi')        -Destination $Dir
    Copy-Item -LiteralPath (Join-Path $CaseDir 'fungi_init_cfg.dat') -Destination $Dir
    $argv = @('input_fungi') + $ModelArgs + @('amr.plot_int=-1','amr.check_int=-1')
    if ($Ranks -gt 1) { $program = $BmxTool2.MpiExec; $argv = @('-n', "$Ranks", $Exe) + $argv }
    else              { $program = $Exe }
    # Hard timeout. A branch-forcing parameter can make the implicit solve
    # intractable rather than merely fast-failing, which is exactly what an
    # earlier k=1e6 attempt did. A hung fixture must be recorded as TIMEOUT,
    # never left to stall the stage.
    $log = Join-Path $Dir 'stdout.log'
    $err = Join-Path $Dir 'stderr.log'
    # Two Start-Process traps, both hit for real and both silently corrupting:
    #
    # 1. -ArgumentList with an ARRAY mangles the arguments: the model ignored
    #    every `name=value` override and ran to the inputs-file default of
    #    200000 steps (observed: a 20-step fixture reached step 2454). Passing a
    #    single pre-joined string is parsed correctly.
    # 2. The timed WaitForExit overload returns $false immediately unless the
    #    process Handle has been touched first -- so every run looked like a
    #    TIMEOUT even when it had already exited cleanly.
    $p = Start-Process -FilePath $program -ArgumentList ($argv -join ' ') -WorkingDirectory $Dir `
                       -RedirectStandardOutput $log -RedirectStandardError $err `
                       -NoNewWindow -PassThru
    $null = $p.Handle
    if ($p.WaitForExit($TimeoutSeconds * 1000)) {
        $code = $p.ExitCode
    } else {
        try { $p.Kill() } catch { }
        $p.WaitForExit(10000) | Out-Null
        Write-Host ("    TIMEOUT after {0}s -- killed" -f $TimeoutSeconds)
        $code = 'TIMEOUT'
    }
    # Guard against silently-dropped overrides.
    #
    # Two separate bugs in this harness caused the model to ignore every
    # `name=value` argument and run to the inputs-file default of 200000 steps
    # (an array -ArgumentList, then an $Args parameter-name collision). Both
    # produced plausible-looking TIMEOUTs that could have been written up as
    # "the branch-forcing parameters are numerically intractable".
    #
    # So do not trust that the arguments arrived: prove it from the output. If a
    # max_step override was requested, the log must not contain a later step.
    $requested = ($ModelArgs | Where-Object { $_ -like 'bmx.max_step=*' } |
                  ForEach-Object { [int]($_ -split '=')[1] } | Select-Object -First 1)
    if ($null -ne $requested -and (Test-Path -LiteralPath $log)) {
        $lastStep = Select-String -LiteralPath $log -Pattern '^\s*Step (\d+):' |
                    ForEach-Object { [int]$_.Matches[0].Groups[1].Value } |
                    Measure-Object -Maximum | Select-Object -ExpandProperty Maximum
        if ($null -ne $lastStep -and $lastStep -gt $requested) {
            throw ("override was dropped: requested bmx.max_step=$requested but the run reached step $lastStep. " +
                   "The arguments are not reaching the model; fix the harness before trusting any fixture result.")
        }
    }

    return @{ exit = $code; log = $log }
}

# mpiexec is needed for the 2-rank control.
. (Join-Path $scriptDir 'native_windows_env.ps1')
$BmxTool2 = $BmxTool

$results = @()
foreach ($f in $fixtures) {
    $ranks = if ($f.ContainsKey('ranks')) { [int]$f.ranks } else { 1 }
    $fdir  = Join-Path $OutRoot $f.id
    Write-Host ("--- {0}  [{1}]  expect {2}" -f $f.id, $f.hook, $f.expect)
    Write-Host ("    {0}" -f $f.desc)

    $b = Invoke-Tree -Exe $BaselineExe -Dir (Join-Path $fdir 'baseline') -ModelArgs $f.args -Ranks $ranks -TimeoutSeconds $TimeoutSeconds
    $r = Invoke-Tree -Exe $RepairedExe -Dir (Join-Path $fdir 'repaired') -ModelArgs $f.args -Ranks $ranks -TimeoutSeconds $TimeoutSeconds

    Write-Host ("    baseline exit={0}  repaired exit={1}" -f $b.exit, $r.exit)

    $results += [pscustomobject]@{
        id            = $f.id
        hook          = $f.hook
        description   = $f.desc
        expectation   = $f.expect
        ranks         = $ranks
        arguments     = $f.args
        baseline_exit = $b.exit
        repaired_exit = $r.exit
        baseline_log  = $b.log
        repaired_log  = $r.log
    }
}

$results | ConvertTo-Json -Depth 6 | Out-File -FilePath (Join-Path $OutRoot 'FIXTURE_INDEX.json') -Encoding utf8
Write-Host ''
Write-Host "fixtures run : $($results.Count)"
Write-Host "index        : $(Join-Path $OutRoot 'FIXTURE_INDEX.json')"
Write-Host 'Comparison is performed by tools/repro/compare_p07_fixtures.py'
