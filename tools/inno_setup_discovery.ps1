Set-StrictMode -Version Latest

function Get-OptionalPropertyValue {
    param([object]$InputObject, [Parameter(Mandatory)][string]$Name)

    $property = $InputObject.PSObject.Properties[$Name]
    if ($property) { return $property.Value }
    return $null
}

function Get-InnoSetupVersion {
    param([Parameter(Mandatory)][string]$Path)

    $item = Get-Item -LiteralPath $Path -ErrorAction Stop
    foreach ($value in @($item.VersionInfo.ProductVersion, $item.VersionInfo.FileVersion)) {
        if ($value -and $value -match '^\s*(\d+\.\d+(?:\.\d+){0,2})') {
            if ($Matches[1] -ne '0.0.0.0') { return $Matches[1] }
        }
    }

    $installDirectory = Split-Path -Parent $item.FullName
    foreach ($registryPath in @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )) {
        foreach ($entry in (Get-ItemProperty $registryPath -ErrorAction SilentlyContinue)) {
            $displayName = Get-OptionalPropertyValue $entry 'DisplayName'
            $entryInstallLocation = Get-OptionalPropertyValue $entry 'InstallLocation'
            if ($displayName -match '^Inno Setup\s+\d+(?:\.\d+)*$' -and
                $entryInstallLocation -and
                [string]::Equals(
                    [IO.Path]::GetFullPath($entryInstallLocation).TrimEnd('\'),
                    $installDirectory.TrimEnd('\'),
                    [StringComparison]::OrdinalIgnoreCase)) {
                return Get-OptionalPropertyValue $entry 'DisplayVersion'
            }
        }
    }

    $banner = @(& $item.FullName '/?' 2>&1 | Select-Object -First 1)
    if ($banner -match '^Inno Setup\s+(\d+)\s+Command-Line Compiler') {
        return $Matches[1]
    }
    throw "Could not determine the Inno Setup version for: $($item.FullName)"
}

function Assert-InnoSetup7Compiler {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Version
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Inno Setup compiler file was not found: $Path"
    }
    $item = Get-Item -LiteralPath $Path -ErrorAction Stop
    if ($item.Name -cne 'ISCC.exe') {
        throw "Expected a file named ISCC.exe, got: $($item.FullName)"
    }
    if ($Path -notmatch '^(?:[A-Za-z]:\\|\\\\)') {
        throw "QUOTATRAY_ISCC must be a full path to ISCC.exe: $Path"
    }
    if ($Version -notmatch '^\s*(\d+)(?:\.\d+(?:\.\d+){0,2})?(?:\b|\s)') {
        throw "Could not parse the Inno Setup version '$Version' for: $($item.FullName)"
    }
    if ($Matches[1] -ne '7') {
        throw "Inno Setup 7 is required; found version $Version at $($item.FullName)"
    }

    [pscustomobject]@{ Path = $item.FullName; Version = $Version.Trim() }
}

function Get-InnoSetupCandidates {
    $candidates = [System.Collections.Generic.List[object]]::new()
    $registryPaths = @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )
    foreach ($registryPath in $registryPaths) {
        foreach ($entry in (Get-ItemProperty $registryPath -ErrorAction SilentlyContinue)) {
            $displayName = Get-OptionalPropertyValue $entry 'DisplayName'
            $entryInstallLocation = Get-OptionalPropertyValue $entry 'InstallLocation'
            if ($displayName -match '^Inno Setup\s+\d+(?:\.\d+)*$' -and $entryInstallLocation) {
                $candidates.Add([pscustomobject]@{
                    Path = Join-Path $entryInstallLocation 'ISCC.exe'
                    Version = Get-OptionalPropertyValue $entry 'DisplayVersion'
                })
            }
        }
    }

    foreach ($directory in @(
        (Join-Path $env:ProgramFiles 'Inno Setup 7'),
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 7'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7')
    )) {
        if ($directory) {
            $candidates.Add([pscustomobject]@{ Path = Join-Path $directory 'ISCC.exe'; Version = $null })
        }
    }

    foreach ($command in @(Get-Command ISCC.exe -All -ErrorAction SilentlyContinue)) {
        $candidates.Add([pscustomobject]@{ Path = $command.Source; Version = $null })
    }

    $seen = @{}
    foreach ($candidate in $candidates) {
        $key = [string]$candidate.Path
        if (-not $seen.ContainsKey($key)) {
            $seen[$key] = $true
            $candidate
        }
    }
}

function Resolve-InnoSetup7Compiler {
    param(
        [string]$ExplicitPath = $env:QUOTATRAY_ISCC,
        [object[]]$Candidates = $null,
        [scriptblock]$VersionResolver = $null
    )

    if ($ExplicitPath) {
        if (-not (Test-Path -LiteralPath $ExplicitPath -PathType Leaf)) {
            throw "Inno Setup compiler file was not found: $ExplicitPath"
        }
        if (-not $VersionResolver) { $VersionResolver = { param($path) Get-InnoSetupVersion -Path $path } }
        $version = & $VersionResolver $ExplicitPath
        return Assert-InnoSetup7Compiler -Path $ExplicitPath -Version $version
    }

    if ($null -eq $Candidates) { $Candidates = @(Get-InnoSetupCandidates) }
    if (-not $VersionResolver) { $VersionResolver = { param($path) Get-InnoSetupVersion -Path $path } }
    foreach ($candidate in $Candidates) {
        if (-not (Test-Path -LiteralPath $candidate.Path -PathType Leaf)) { continue }
        try {
            $version = if ($candidate.Version) { $candidate.Version } else { & $VersionResolver $candidate.Path }
            return Assert-InnoSetup7Compiler -Path $candidate.Path -Version $version
        } catch {
            Write-Verbose $_.Exception.Message
        }
    }

    throw @'
Inno Setup 7 was not found.

Install the official 64-bit Inno Setup 7 package:

winget install --id JRSoftware.InnoSetup.7 -e -s winget -i

Or set QUOTATRAY_ISCC to the full path of ISCC.exe.
'@
}
