# BMX RG-SW — native Windows toolchain resolution.
#
# Dot-source this file. It resolves every required tool path, fails loudly if
# any is absent, and imports the MSVC developer environment into the current
# PowerShell session so that cl.exe can find its headers and libraries.
#
# It sets: $BmxTool (hashtable of resolved paths).
#
# Note: this repository is checked out with core.fileMode=false, so no script
# here may depend on a working-tree executable bit. Always invoke through an
# explicit interpreter (powershell -File ..., sh ..., python ...).

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-RequiredPath {
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)][string]$What)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "required build prerequisite is absent: $What`n  expected at: $Path"
    }
    return (Resolve-Path -LiteralPath $Path).Path
}

# --- Locate the MSVC toolchain ------------------------------------------------
#
# vswhere alone is NOT trustworthy on this host. The Build Tools installation
# was renamed from 'C:\Program' to 'C:\Program1' during the C03 stage, and
# vswhere kept serving the OLD path while flipping the instance to
# isComplete:false -- so `-latest` returned nothing at all and `-all` returned a
# path that no longer exists. Either way the answer was useless.
#
# Resolution order, each candidate VALIDATED by the presence of vcvars64.bat
# before it is accepted:
#   1. $env:BMX_VS_ROOT             -- explicit override, wins outright
#   2. vswhere (-latest, then -all) -- but only if the path really exists
#   3. directory scan               -- top level of C:\ and the Program Files
#
# Never accept a path from vswhere without checking it on disk.

function Test-VsRoot {
    param([string]$Candidate)
    if ([string]::IsNullOrWhiteSpace($Candidate)) { return $false }
    return (Test-Path -LiteralPath (Join-Path $Candidate 'VC\Auxiliary\Build\vcvars64.bat'))
}

$vsRoot     = $null
$vsSource   = $null
$vsAttempts = @()

if ($env:BMX_VS_ROOT) {
    $vsAttempts += "BMX_VS_ROOT=$env:BMX_VS_ROOT"
    if (Test-VsRoot $env:BMX_VS_ROOT) { $vsRoot = $env:BMX_VS_ROOT; $vsSource = 'BMX_VS_ROOT override' }
    else { throw "BMX_VS_ROOT is set to '$env:BMX_VS_ROOT' but that is not a Visual Studio installation root (no VC\Auxiliary\Build\vcvars64.bat)" }
}

if (-not $vsRoot) {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (Test-Path -LiteralPath $vswhere) {
        foreach ($argSet in @(@('-products','*','-latest','-property','installationPath'),
                              @('-all','-products','*','-property','installationPath'))) {
            $candidates = @(& $vswhere @argSet 2>$null | ForEach-Object { $_.Trim() } | Where-Object { $_ })
            foreach ($c in $candidates) {
                $vsAttempts += "vswhere -> $c"
                if (Test-VsRoot $c) { $vsRoot = $c; $vsSource = 'vswhere'; break }
            }
            if ($vsRoot) { break }
        }
    } else { $vsAttempts += 'vswhere.exe not present' }
}

if (-not $vsRoot) {
    $scanRoots = @('C:\', $env:ProgramFiles, ${env:ProgramFiles(x86)}) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
    foreach ($sr in $scanRoots) {
        $found = Get-ChildItem -LiteralPath $sr -Directory -Force -ErrorAction SilentlyContinue |
                 Where-Object { Test-VsRoot $_.FullName } |
                 Select-Object -First 1 -ExpandProperty FullName
        if ($found) { $vsAttempts += "scan $sr -> $found"; $vsRoot = $found; $vsSource = "directory scan of $sr"; break }
        $vsAttempts += "scan $sr -> nothing"
    }
}

if (-not $vsRoot) {
    throw ("no usable Visual Studio / Build Tools installation was found.`n" +
           "Tried:`n  " + ($vsAttempts -join "`n  ") + "`n" +
           "Set BMX_VS_ROOT to the installation root (the directory containing VC\Auxiliary\Build\vcvars64.bat).")
}

$msvcRoot = Resolve-RequiredPath (Join-Path $vsRoot 'VC\Tools\MSVC') 'MSVC toolset directory'
$msvcVer  = (Get-ChildItem -LiteralPath $msvcRoot -Directory |
             Sort-Object Name -Descending | Select-Object -First 1).Name
if (-not $msvcVer) { throw "no MSVC toolset version found under $msvcRoot" }

$BmxTool = @{}
$BmxTool.VsRoot    = $vsRoot
$BmxTool.MsvcVer   = $msvcVer
$BmxTool.Cl        = Resolve-RequiredPath (Join-Path $msvcRoot "$msvcVer\bin\Hostx64\x64\cl.exe") 'MSVC C/C++ compiler (cl.exe)'
$BmxTool.Ninja     = Resolve-RequiredPath (Join-Path $vsRoot 'Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe') 'Ninja generator'
$BmxTool.VcVars    = Resolve-RequiredPath (Join-Path $vsRoot 'VC\Auxiliary\Build\vcvars64.bat') 'vcvars64.bat'
$BmxTool.CMake     = Resolve-RequiredPath 'C:\Program Files\CMake\bin\cmake.exe' 'CMake'
$BmxTool.MpiInc    = Resolve-RequiredPath (Join-Path ${env:ProgramFiles(x86)} 'Microsoft SDKs\MPI\Include') 'MS-MPI SDK include directory'
$BmxTool.MpiLib    = Resolve-RequiredPath (Join-Path ${env:ProgramFiles(x86)} 'Microsoft SDKs\MPI\Lib\x64\msmpi.lib') 'MS-MPI import library'
$BmxTool.MpiExec   = Resolve-RequiredPath (Join-Path $env:ProgramFiles 'Microsoft MPI\Bin\mpiexec.exe') 'MS-MPI mpiexec'

# rc.exe: pick the newest Windows SDK x64 bin directory that actually has it.
$rcCandidates = @(Get-ChildItem -LiteralPath (Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin') `
                    -Directory -ErrorAction SilentlyContinue |
                  Sort-Object Name -Descending |
                  ForEach-Object { Join-Path $_.FullName 'x64\rc.exe' } |
                  Where-Object { Test-Path -LiteralPath $_ })
if ($rcCandidates.Count -eq 0) { throw 'required build prerequisite is absent: rc.exe (Windows SDK resource compiler)' }
$BmxTool.Rc = $rcCandidates[0]
$BmxTool.Mt = Resolve-RequiredPath (Join-Path (Split-Path -Parent $BmxTool.Rc) 'mt.exe') 'Windows SDK manifest tool (mt.exe)'

# Import the MSVC developer environment (INCLUDE / LIB / PATH) into this session.
# cl.exe cannot locate the CRT or Windows SDK headers without it.
if (-not $env:BMX_VCVARS_IMPORTED) {
    $tmp = [System.IO.Path]::GetTempFileName()
    try {
        & "$env:ComSpec" /s /c "`"$($BmxTool.VcVars)`" >nul 2>&1 && set" |
            Out-File -FilePath $tmp -Encoding ascii
        if ($LASTEXITCODE -ne 0) { throw "vcvars64.bat failed with exit code $LASTEXITCODE" }
        Get-Content -LiteralPath $tmp | ForEach-Object {
            if ($_ -match '^([^=]+)=(.*)$') {
                Set-Item -Path ("Env:" + $matches[1]) -Value $matches[2] -ErrorAction SilentlyContinue
            }
        }
        $env:BMX_VCVARS_IMPORTED = '1'
    } finally { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
}

# --- POSIX text utilities required by the build system itself -----------------
# tools/CMake/BMX_Utils.cmake:8 runs `git branch | grep \*` to stamp the branch
# name. `grep` is not a Windows command, so on a bare Windows host that pipeline
# yields empty output and the following string(REPLACE ...) aborts configure
# with "requires at least four arguments". Git for Windows ships a real grep;
# put it on PATH.
#
# APPEND, never prepend. Git's usr/bin also contains link.exe, sort.exe and
# find.exe, which would shadow the MSVC linker and the Windows sort/find that
# vcvars just put in front. Appending resolves grep while leaving every MSVC
# tool ahead of the MSYS copies.
$gitUsrBin = Join-Path $env:ProgramFiles 'Git\usr\bin'
if ((Test-Path -LiteralPath $gitUsrBin) -and ($env:PATH -notlike "*$gitUsrBin*")) {
    $env:PATH = $env:PATH.TrimEnd(';') + ';' + $gitUsrBin
}
$BmxTool.Grep = Resolve-RequiredPath (Join-Path $gitUsrBin 'grep.exe') 'grep.exe (needed by tools/CMake/BMX_Utils.cmake)'

# The installation root is embedded in build output (AMReX build-info banner and
# every absolute path in compile_commands.json), so moving or renaming it changes
# the resulting bmx.exe hash even with identical source and flags. Report which
# root was used and how it was found, so a hash mismatch across stages can be
# attributed rather than guessed at.
Write-Host "VS root      : $vsRoot  (via $vsSource)"
Write-Host "MSVC toolset : $($BmxTool.MsvcVer)"
Write-Host "cl.exe       : $($BmxTool.Cl)"
Write-Host "ninja        : $($BmxTool.Ninja)"
Write-Host "rc.exe       : $($BmxTool.Rc)"
Write-Host "mt.exe       : $($BmxTool.Mt)"
Write-Host "cmake        : $($BmxTool.CMake)"
Write-Host "MS-MPI inc   : $($BmxTool.MpiInc)"
Write-Host "MS-MPI lib   : $($BmxTool.MpiLib)"
