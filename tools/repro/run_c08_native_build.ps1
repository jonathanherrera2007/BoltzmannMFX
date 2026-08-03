# Configure and build C08 in a fresh, stage-specific native Windows tree.
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
$sourceHeadBeforeBuild = (& git -C $source rev-parse HEAD).Trim()
$sourceTreeBeforeBuild = (& git -C $source rev-parse 'HEAD^{tree}').Trim()
$sourceDirtyBeforeBuild = [bool](& git -C $source status --porcelain)
$build = [System.IO.Path]::GetFullPath($BuildDir)
$allowedParent = [System.IO.Path]::GetFullPath((Split-Path -Parent $source)).TrimEnd('\') + '\'
if (-not $build.StartsWith($allowedParent, [System.StringComparison]::OrdinalIgnoreCase) -or
    $build.Equals($source, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "C08 build directory must be a distinct path below $allowedParent; got $build"
}

$log = [System.IO.Path]::GetFullPath($LogPath)
$json = [System.IO.Path]::GetFullPath($JsonOut)
$captureLog = $build + '.native_build.log'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $log) | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $json) | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $captureLog) | Out-Null

$configure = Join-Path $source 'tools\repro\configure_native_windows.ps1'
$buildScript = Join-Path $source 'tools\repro\build_native_windows.ps1'

Set-Content -LiteralPath $captureLog -Encoding utf8 -Value @(
    'C08_NATIVE_BUILD_LOG_V1'
    "source=$source"
    "build=$build"
)

function Invoke-CapturedPowerShell(
    [string]$Label,
    [string[]]$Arguments
) {
    Add-Content -LiteralPath $captureLog -Encoding utf8 -Value "BEGIN $Label"
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & powershell.exe @Arguments 2>&1 | ForEach-Object {
            $line = $_.ToString()
            Write-Host $line
            Add-Content -LiteralPath $captureLog -Encoding utf8 -Value $line
        }
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorAction
    }
    Add-Content -LiteralPath $captureLog -Encoding utf8 -Value "END $Label exit_code=$exitCode"
    if ($exitCode -ne 0) { throw "C08 $Label failed: $exitCode" }
}

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
if (-not (Test-Path -LiteralPath $exe)) { throw "fresh build did not produce $exe" }

$cacheText = Get-Content -Raw -LiteralPath $cache
function Cache-Value([string]$Name) {
    $match = [regex]::Match($cacheText, "(?m)^$([regex]::Escape($Name)):[^=]+=(.*)$")
    if (-not $match.Success) { return $null }
    return $match.Groups[1].Value.Trim()
}

$record = [ordered]@{
    artifact_type = 'C08_NATIVE_BUILD'
    stage = 'C08'
    status = 'PASS'
    source = [ordered]@{
        path = $source
        head = $sourceHeadBeforeBuild
        tree = $sourceTreeBeforeBuild
        dirty = $sourceDirtyBeforeBuild
        status_capture = 'before build evidence outputs were opened'
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
    frozen_kernel_sha256 = (Get-FileHash -LiteralPath (Join-Path $source 'src\chemistry\bmx_chem_K.H') -Algorithm SHA256).Hash.ToLower()
    executable = [ordered]@{
        path = $exe
        size_bytes = (Get-Item -LiteralPath $exe).Length
        sha256 = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLower()
    }
    commands = @(
        "powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/repro/configure_native_windows.ps1 -SourceDir $source -BuildDir $build -Fresh"
        "powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/repro/build_native_windows.ps1 -BuildDir $build -Target bmx -Parallel $Parallel"
    )
    raw_log = $log
    raw_log_sha256 = (Get-FileHash -LiteralPath $captureLog -Algorithm SHA256).Hash.ToLower()
    cmake_cache_sha256 = (Get-FileHash -LiteralPath $cache -Algorithm SHA256).Hash.ToLower()
    external_resources = 'none'
    external_spend_usd = 0
}
Copy-Item -LiteralPath $captureLog -Destination $log -Force
$jsonText = ($record | ConvertTo-Json -Depth 8) + [Environment]::NewLine
[System.IO.File]::WriteAllText(
    $json,
    $jsonText,
    [System.Text.UTF8Encoding]::new($false)
)
Write-Host "C08 native build evidence: $json"
