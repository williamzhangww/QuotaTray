<#
.SYNOPSIS
    Build, verify, and package QuotaTray for a release.

.DESCRIPTION
    Enforces the toolchain that produced the known-good v0.7.0 payload
    (Python 3.10.11 + PySide6 6.11.2 + PyInstaller 6.22.3) and runs the frozen
    payload check that guards against the v0.7.1 QtCore/ICU regression.

    Steps:
      1. preflight   - toolchain versions, ICU pollution report
      2. tests       - pytest
      3. pyinstaller - clean onedir build (dist/)
      4. verify      - tools/verify_frozen.py must PASS
      5. installer   - Inno Setup 7 -> release/QuotaTray-<ver>-Setup.exe
      6. hashes      - SHA256 of release artifacts

.PARAMETER SkipTests
    Skip the pytest step.

.PARAMETER SkipInstaller
    Stop after the verified dist build (do not build the installer).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File tools\build_release.ps1
#>
[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# With $ErrorActionPreference='Stop', PowerShell 7 promotes *any* stderr output
# from a native command to a terminating error. PyInstaller and pytest write
# ordinary progress to stderr, so run native tools with stderr tolerated and
# check $LASTEXITCODE explicitly instead.
function Invoke-Native {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory)][string[]]$Arguments
    )
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $FilePath @Arguments 2>&1 | ForEach-Object { Write-Host $_ }
    } finally {
        $ErrorActionPreference = $previous
    }
    return $LASTEXITCODE
}

# $PSScriptRoot is empty when this file is dot-sourced or run as a scriptblock.
$root = if ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot } else { (Get-Location).Path }
$defaultPython = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python310\python.exe'
$python = if ($env:QUOTATRAY_PYTHON) {
    $env:QUOTATRAY_PYTHON
} elseif (Test-Path $defaultPython) {
    $defaultPython
} else {
    (Get-Command python).Source
}
$innoDiscoveryModule = Join-Path $root 'tools\inno_setup_discovery.ps1'
$distPayload = Join-Path $root 'dist\QuotaTray'

if (-not (Test-Path $python)) { throw "Python 3.10.11 not found: $python" }

$pythonInfo = @(& $python -c "import sys; print(sys.version.split()[0]); print(sys.prefix); print(sys.base_prefix)")
if ($LASTEXITCODE -ne 0 -or $pythonInfo[0].Trim() -ne '3.10.11') {
    throw "Release builds require Python 3.10.11; selected $python ($($pythonInfo[0]))."
}
$pythonPrefix = $pythonInfo[1].Trim()
$pythonBasePrefix = $pythonInfo[2].Trim()

$version = (& $python -c "import sys; sys.path.insert(0, r'$root\src'); from codex_usage_monitor.version import __version__; print(__version__)").Trim()
Write-Host "=== QuotaTray $version release build ===" -ForegroundColor Cyan

# Build and test with an explicit PATH. In particular, do not inherit the
# agent/Codex runtime, Poppler, libheif, or Conda entries which can make
# PyInstaller resolve Windows API-set/UCRT imports to unrelated DLL copies.
$safePath = @(
    $pythonPrefix,
    $pythonBasePrefix,
    (Join-Path $pythonPrefix 'Scripts'),
    (Join-Path $pythonPrefix 'DLLs'),
    (Join-Path $pythonPrefix 'Lib\site-packages\PySide6'),
    (Join-Path $pythonPrefix 'Lib\site-packages\shiboken6'),
    (Join-Path $env:SystemRoot 'System32'),
    $env:SystemRoot,
    (Join-Path $env:SystemRoot 'System32\Wbem'),
    (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0'),
    (Join-Path $env:SystemRoot 'System32\OpenSSH')
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -Unique
$env:PATH = $safePath -join ';'
$env:PYTHONNOUSERSITE = '1'
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
Remove-Item Env:QT_PLUGIN_PATH -ErrorAction SilentlyContinue
Remove-Item Env:QT_QPA_PLATFORM_PLUGIN_PATH -ErrorAction SilentlyContinue
Remove-Item Env:QT_QPA_FONTDIR -ErrorAction SilentlyContinue
Remove-Item Env:QML2_IMPORT_PATH -ErrorAction SilentlyContinue
Remove-Item Env:QML_IMPORT_PATH -ErrorAction SilentlyContinue
Write-Host 'Controlled build PATH enabled; Codex runtime, Poppler, libheif, Conda, and unrelated application paths are excluded.' -ForegroundColor Green

. $innoDiscoveryModule
$innoCompiler = Resolve-InnoSetup7Compiler
$isccHash = (Get-FileHash -LiteralPath $innoCompiler.Path -Algorithm SHA256).Hash
Write-Host "Inno Setup compiler: $($innoCompiler.Path)"
Write-Host "Inno Setup version: $($innoCompiler.Version)"
Write-Host "ISCC SHA256: $isccHash"

# --------------------------------------------------------------------------
# 1. Preflight
# --------------------------------------------------------------------------
Write-Host "`n--- [1/6] preflight ---" -ForegroundColor Cyan

$preflight = @"
import sys
import importlib.metadata as md
print('python        ', sys.version.split()[0], '->', sys.executable)
assert sys.version_info[:2] == (3, 10), 'Release requires Python 3.10'
for pkg in ('PySide6', 'shiboken6', 'pyinstaller', 'pyinstaller-hooks-contrib'):
    try:
        print('%-14s' % pkg, md.version(pkg))
    except Exception:
        print('%-14s' % pkg, 'MISSING')
for pkg in ('PySide6', 'shiboken6', 'pyinstaller'):
    md.version(pkg)  # Missing release dependencies must fail preflight.
"@
$rc = Invoke-Native -FilePath $python -Arguments @('-c', $preflight)
if ($rc -ne 0) { throw 'Python interpreter check failed' }

# Report (not fail on) PATH entries that ship a foreign ICU. The spec's ICU
# guard drops them from the payload, but it is worth knowing they are visible.
$icuOnPath = @()
foreach ($dir in ($env:PATH -split ';' | Where-Object { $_ })) {
    if (Test-Path (Join-Path $dir 'icuuc.dll') -ErrorAction SilentlyContinue) {
        $resolvedDir = [IO.Path]::GetFullPath($dir).TrimEnd('\')
        $system32Dir = [IO.Path]::GetFullPath((Join-Path $env:SystemRoot 'System32')).TrimEnd('\')
        if (-not [string]::Equals($resolvedDir, $system32Dir, [StringComparison]::OrdinalIgnoreCase)) {
            $icuOnPath += $dir
        }
    }
}
if ($icuOnPath.Count -gt 0) {
    Write-Host '  note: foreign ICU visible on PATH (spec ICU guard will drop it):' -ForegroundColor Yellow
    $icuOnPath | Sort-Object -Unique | ForEach-Object { Write-Host "        $_" -ForegroundColor Yellow }
} else {
    Write-Host '  ok: no foreign ICU on PATH' -ForegroundColor Green
}

# --------------------------------------------------------------------------
# 2. Tests
# --------------------------------------------------------------------------
if (-not $SkipTests) {
    Write-Host "`n--- [2/6] source tests ---" -ForegroundColor Cyan
    Push-Location $root
    try {
        # pytest uses %TEMP%\pytest-of-<user> for scratch dirs; if that tree has
        # a broken ACL (seen on this machine), redirect to a fresh basetemp
        # rather than failing with PermissionError.
        $pytestArgs = @('-m', 'pytest', '-q')
        $userTemp = Join-Path $env:TEMP ("pytest-of-" + $env:USERNAME)
        $probe = Join-Path $userTemp ('.probe-' + [guid]::NewGuid().ToString('N').Substring(0, 6))
        $tempUsable = $true
        try {
            New-Item -ItemType Directory -Path $probe -Force -ErrorAction Stop | Out-Null
            Remove-Item $probe -Recurse -Force
        } catch {
            $tempUsable = $false
        }
        if (-not $tempUsable) {
            $alt = Join-Path $env:TEMP ('cum-pytest-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
            Write-Host "  note: $userTemp is not writable; using --basetemp=$alt" -ForegroundColor Yellow
            $pytestArgs += "--basetemp=$alt"
        }
        $rc = Invoke-Native -FilePath $python -Arguments $pytestArgs
        if ($rc -ne 0) { throw 'pytest failed' }
    } finally { Pop-Location }
} else {
    Write-Host "`n--- [2/6] source tests (skipped) ---" -ForegroundColor DarkGray
}

# --------------------------------------------------------------------------
# 3. Clean PyInstaller build
# --------------------------------------------------------------------------
Write-Host "`n--- [3/6] clean PyInstaller build ---" -ForegroundColor Cyan
Push-Location $root
try {
    # build/version_info.txt is a *generated input* consumed by the spec via
    # EXE(version=...), not a PyInstaller artifact. Regenerate it before
    # cleaning, and never delete the whole build/ directory.
    $rc = Invoke-Native -FilePath $python -Arguments @('tools\generate_release_metadata.py')
    if ($rc -ne 0) { throw 'release metadata generation failed' }

    foreach ($path in @('build\QuotaTray', 'dist')) {
        if (Test-Path $path) {
            $resolved = (Resolve-Path -LiteralPath $path).Path
            if (-not $resolved.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) {
                throw "Cleanup target outside workspace: $resolved"
            }
            Remove-Item -LiteralPath $resolved -Recurse -Force
            Write-Host "  removed $path"
        }
    }
    $rc = Invoke-Native -FilePath $python -Arguments @('-m', 'PyInstaller', '--noconfirm', '--clean', 'QuotaTray.spec')
    if ($rc -ne 0) { throw 'PyInstaller failed' }
} finally { Pop-Location }

# --------------------------------------------------------------------------
# 4. Verify frozen payload
# --------------------------------------------------------------------------
Write-Host "`n--- [4/6] verify frozen payload ---" -ForegroundColor Cyan
$collectToc = Join-Path $root 'build\QuotaTray\COLLECT-00.toc'
$rc = Invoke-Native -FilePath $python -Arguments @((Join-Path $root 'tools\verify_frozen.py'), $distPayload, '--toc', $collectToc)
if ($rc -ne 0) {
    throw 'Frozen payload verification FAILED - refusing to build an installer'
}

# --------------------------------------------------------------------------
# 5. Installer
# --------------------------------------------------------------------------
$setup = Join-Path $root "release\QuotaTray-$version-Setup.exe"
if (-not ('ReleaseIntegrity' -as [type])) {
    Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class ReleaseIntegrity {
    [DllImport("advapi32.dll", CharSet=CharSet.Unicode)]
    static extern uint GetNamedSecurityInfo(string name, int type, uint info,
        out IntPtr owner, out IntPtr group, out IntPtr dacl, out IntPtr sacl, out IntPtr sd);
    [DllImport("advapi32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern bool ConvertSecurityDescriptorToStringSecurityDescriptor(
        IntPtr sd, uint revision, uint info, out IntPtr text, out uint length);
    [DllImport("kernel32.dll")] static extern IntPtr LocalFree(IntPtr memory);
    public static string Read(string path) {
        IntPtr owner, group, dacl, sacl, sd, text;
        uint result = GetNamedSecurityInfo(path, 1, 0x10, out owner, out group, out dacl, out sacl, out sd);
        if (result != 0) throw new System.ComponentModel.Win32Exception((int)result);
        try {
            uint length;
            if (!ConvertSecurityDescriptorToStringSecurityDescriptor(sd, 1, 0x10, out text, out length))
                throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
            try { return Marshal.PtrToStringUni(text); } finally { LocalFree(text); }
        } finally { LocalFree(sd); }
    }
}
'@
}
if (-not $SkipInstaller) {
    Write-Host "`n--- [5/6] Inno Setup installer ---" -ForegroundColor Cyan
    $compilerDirectory = Split-Path -Parent $innoCompiler.Path
    $savedPath = $env:PATH
    $env:PATH = @($compilerDirectory, (Join-Path $env:SystemRoot 'System32'), $env:SystemRoot) -join ';'
    Push-Location (Join-Path $root 'installer')
    try {
        $helpExit = Invoke-Native -FilePath $innoCompiler.Path -Arguments @('/?')
        if ($helpExit -ne 0) { throw "ISCC /? failed with exit code $helpExit" }
        Write-Host 'ISCC /?: PASS'
        $rc = Invoke-Native -FilePath $innoCompiler.Path -Arguments @('QuotaTray.iss')
        if ($rc -ne 0) { throw 'Inno Setup compile failed' }
    } finally { Pop-Location; $env:PATH = $savedPath }
    if (-not (Test-Path $setup)) { throw "installer not produced: $setup" }
} else {
    Write-Host "`n--- [5/6] installer (skipped) ---" -ForegroundColor DarkGray
}

# --------------------------------------------------------------------------
# 6. Hashes
# --------------------------------------------------------------------------
Write-Host "`n--- [6/6] artifact hashes ---" -ForegroundColor Cyan
if (Test-Path $setup) {
    $item = Get-Item $setup
    $hash = (Get-FileHash $setup -Algorithm SHA256).Hash
    Write-Host ("  {0}" -f $item.Name)
    Write-Host ("    size   {0:N0} bytes" -f $item.Length)
    Write-Host ("    sha256 {0}" -f $hash)
}

if (-not $SkipInstaller) {
    # Copy bytes into a newly created file so security metadata from a Low
    # workspace is not copied. Do not change either directory's ACL/label.
    $safeDir = Join-Path $env:USERPROFILE "QuotaTray-Releases\v$version"
    New-Item -ItemType Directory -Path $safeDir -Force | Out-Null
    $safeSetup = Join-Path $safeDir (Split-Path -Leaf $setup)
    $staging = Join-Path $safeDir ([guid]::NewGuid().ToString('N') + '.exe')
    $sourceStream = [IO.File]::OpenRead($setup)
    try {
        $destinationStream = [IO.File]::Open($staging, [IO.FileMode]::CreateNew)
        try { $sourceStream.CopyTo($destinationStream) } finally { $destinationStream.Dispose() }
    } finally { $sourceStream.Dispose() }
    Move-Item -LiteralPath $staging -Destination $safeSetup -Force
    $safeHash = (Get-FileHash -LiteralPath $safeSetup -Algorithm SHA256).Hash
    if ($safeHash -ne $hash) { throw 'Desktop-safe installer SHA256 mismatch' }

    # Read mandatory label by SID (locale independent). LABEL_SECURITY_INFORMATION
    # does not require the privilege needed to read the complete audit SACL.
    $label = [ReleaseIntegrity]::Read($safeSetup)
    Write-Host "Desktop-safe installer mandatory label SDDL: $label"
    if ($label -match ';(LW|S-1-16-4096|S-1-16-0)\)') {
        throw 'Desktop-safe installer is Low Integrity (or lower); release FAILED. Workspace ACL was not changed.'
    }
    "$hash  $(Split-Path -Leaf $setup)" | Set-Content -LiteralPath (Join-Path $root 'release\SHA256SUMS.txt') -Encoding ascii
    Write-Host "Version: $version"
    Write-Host "Workspace installer: $setup"
    Write-Host "Desktop-safe installer: $safeSetup"
    Write-Host "SHA256: $hash"
    Write-Host 'Frozen verification: PASS'
    Write-Host 'Bundled ICU: NONE'
    Write-Host 'Desktop-safe installer integrity: not Low'
    Write-Host "INSTALL THIS FILE:`n$safeSetup"
    Write-Host 'Use the desktop-safe installer for installation verification.'
}

Write-Host "`n=== build complete ===" -ForegroundColor Green
