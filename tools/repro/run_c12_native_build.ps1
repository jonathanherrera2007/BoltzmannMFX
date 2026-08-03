# Configure and build C12 from a clean commit in a fresh native Windows tree.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$SourceDir,
    [Parameter(Mandatory)][string]$BuildDir,
    [Parameter(Mandatory)][string]$LogPath,
    [Parameter(Mandatory)][string]$JsonOut,
    [int]$Parallel = 4
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath $SourceDir).Path
$sourceHead = (& git -C $source rev-parse HEAD).Trim()
$sourceTree = (& git -C $source rev-parse 'HEAD^{tree}').Trim()
$sourceStatus = @(& git -C $source status --porcelain=v1 -uall)
if ($sourceStatus.Count -gt 0) {
    throw 'C12 final build requires a clean implementation commit.'
}

$build = [System.IO.Path]::GetFullPath($BuildDir)
$allowedParent = [System.IO.Path]::GetFullPath(
    (Split-Path -Parent $source)
).TrimEnd('\') + '\'
if (-not $build.StartsWith(
        $allowedParent, [System.StringComparison]::OrdinalIgnoreCase
    ) -or $build.Equals($source, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "C12 build directory must be distinct and below $allowedParent; got $build"
}

$log = [System.IO.Path]::GetFullPath($LogPath)
$json = [System.IO.Path]::GetFullPath($JsonOut)
$captureLog = $build + '.native_build.log'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $log) | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $json) | Out-Null
$initialLines = @(
    'C12_NATIVE_BUILD_LOG_V1', "source=$source", "build=$build",
    "source_head=$sourceHead", "source_tree=$sourceTree", 'source_dirty=false'
)
[System.IO.File]::WriteAllLines(
    $captureLog, $initialLines, [System.Text.UTF8Encoding]::new($false)
)

function Invoke-CapturedPowerShell([string]$Label, [string[]]$Arguments) {
    Add-Content -LiteralPath $captureLog -Encoding utf8 -Value "BEGIN $Label"
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & powershell.exe @Arguments 2>&1 | ForEach-Object {
            $line = $_.ToString()
            Write-Host $line
            Add-Content -LiteralPath $captureLog -Encoding utf8 -Value $line
        }
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    Add-Content -LiteralPath $captureLog -Encoding utf8 -Value (
        "END $Label exit_code=$exitCode"
    )
    if ($exitCode -ne 0) { throw "C12 $Label failed: $exitCode" }
}

$configure = Join-Path $source 'tools\repro\configure_native_windows.ps1'
$buildScript = Join-Path $source 'tools\repro\build_native_windows.ps1'
Invoke-CapturedPowerShell 'fresh_configure' @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $configure,
    '-SourceDir', $source, '-BuildDir', $build, '-Fresh'
)
Invoke-CapturedPowerShell 'fresh_build' @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $buildScript,
    '-BuildDir', $build, '-Target', 'bmx', '-Parallel', "$Parallel"
)

$exe = Join-Path $build 'bmx.exe'
$cache = Join-Path $build 'CMakeCache.txt'
if (-not (Test-Path -LiteralPath $exe)) {
    throw "fresh build did not produce $exe"
}
$cacheText = Get-Content -Raw -LiteralPath $cache
function Cache-Value([string]$Name) {
    $match = [regex]::Match(
        $cacheText, "(?m)^$([regex]::Escape($Name)):[^=]+=(.*)$"
    )
    if (-not $match.Success) { return $null }
    return $match.Groups[1].Value.Trim()
}

$contract = Join-Path $source 'contracts\p14\EXPORT_REWARD_CONTRACT_V1.json'
$fit = Join-Path $source 'contracts\p14\OPERATOR_FIT_V1.json'
$order = Join-Path $source 'contracts\p10\OPERATOR_ORDER_V1.json'
$geometry = Join-Path $source 'contracts\p11\GEOMETRY_CONTRACT_V1.json'
$record = [ordered]@{
    artifact_type = 'C12_NATIVE_BUILD'
    stage = 'C12/P14'
    status = 'PASS'
    source = [ordered]@{
        path = $source
        head = $sourceHead
        tree = $sourceTree
        dirty_before_configure = $false
        status_capture = 'before build and before evidence outputs were opened'
    }
    amrex = [ordered]@{
        commit = (& git -C (Join-Path $source 'subprojects\amrex') rev-parse HEAD).Trim()
        tree = (& git -C (Join-Path $source 'subprojects\amrex') rev-parse 'HEAD^{tree}').Trim()
    }
    configuration = [ordered]@{
        build_type = Cache-Value 'CMAKE_BUILD_TYPE'
        cxx_compiler = Cache-Value 'CMAKE_CXX_COMPILER'
        cxx_standard = Cache-Value 'CMAKE_CXX_STANDARD'
        bmx_mpi = Cache-Value 'BMX_MPI'
        bmx_omp = Cache-Value 'BMX_OMP'
        bmx_gpu_backend = Cache-Value 'BMX_GPU_BACKEND'
        amrex_spacedim = Cache-Value 'AMReX_SPACEDIM'
    }
    contracts = [ordered]@{
        export_reward_sha256 = (Get-FileHash -LiteralPath $contract -Algorithm SHA256).Hash.ToLower()
        operator_fit_sha256 = (Get-FileHash -LiteralPath $fit -Algorithm SHA256).Hash.ToLower()
        global_order_sha256 = (Get-FileHash -LiteralPath $order -Algorithm SHA256).Hash.ToLower()
        p11_geometry_sha256 = (Get-FileHash -LiteralPath $geometry -Algorithm SHA256).Hash.ToLower()
    }
    frozen_kernel_sha256 = (Get-FileHash -LiteralPath (
        Join-Path $source 'src\chemistry\bmx_chem_K.H'
    ) -Algorithm SHA256).Hash.ToLower()
    executable = [ordered]@{
        path = $exe
        size_bytes = (Get-Item -LiteralPath $exe).Length
        sha256 = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLower()
    }
    raw_log = $log
    cmake_cache_sha256 = (Get-FileHash -LiteralPath $cache -Algorithm SHA256).Hash.ToLower()
    warnings = @('Inherited MSVC C4244 diagnostics arise only in std::numeric instantiated by pinned AMReX particle I/O; no C12 source warning was emitted.')
    external_resources = 'none'
    external_spend_usd = 0
    claim_boundary = 'Clean Windows native C12 engineering build under USER_ADOPTED_PROVISIONAL_PENDING_MENTOR_OVERRIDE; not mentor approval, calibration, predictive validation, or C13 science.'
}
Copy-Item -LiteralPath $captureLog -Destination $log -Force
$record.raw_log_sha256 = (Get-FileHash -LiteralPath $log -Algorithm SHA256).Hash.ToLower()
[System.IO.File]::WriteAllText(
    $json, (($record | ConvertTo-Json -Depth 8) + [Environment]::NewLine),
    [System.Text.UTF8Encoding]::new($false)
)
Write-Host "C12 native build evidence: $json"
