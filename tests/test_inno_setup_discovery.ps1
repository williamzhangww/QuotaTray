param(
    [Parameter(Mandatory)][string]$ModulePath,
    [Parameter(Mandatory)][string]$ScratchPath
)

$ErrorActionPreference = 'Stop'
. $ModulePath
New-Item -ItemType Directory -Path $ScratchPath -Force | Out-Null
$validCompiler = Join-Path $ScratchPath 'valid\ISCC.exe'
$v6Compiler = Join-Path $ScratchPath 'v6\ISCC.exe'
New-Item -ItemType Directory -Path (Split-Path -Parent $validCompiler) -Force | Out-Null
New-Item -ItemType Directory -Path (Split-Path -Parent $v6Compiler) -Force | Out-Null
[IO.File]::WriteAllText($validCompiler, 'test compiler')
[IO.File]::WriteAllText($v6Compiler, 'test compiler')

$versionResolver = {
    param($Path)
    if ($Path -eq $v6Compiler) { return '6.4.0' }
    return '7.1.0'
}.GetNewClosure()

$accepted = Resolve-InnoSetup7Compiler -ExplicitPath $validCompiler -VersionResolver $versionResolver
if ($accepted.Path -ne [IO.Path]::GetFullPath($validCompiler) -or $accepted.Version -ne '7.1.0') {
    throw 'Inno Setup 7 explicit path was not accepted.'
}

$missingPathRejected = $false
try {
    Resolve-InnoSetup7Compiler -ExplicitPath (Join-Path $ScratchPath 'missing\ISCC.exe') -VersionResolver $versionResolver
} catch {
    $missingPathRejected = $_.Exception.Message -like '*compiler file was not found*'
}
if (-not $missingPathRejected) { throw 'A missing explicit compiler path was not rejected clearly.' }

$v6Rejected = $false
try {
    Resolve-InnoSetup7Compiler -ExplicitPath $v6Compiler -VersionResolver $versionResolver
} catch {
    $v6Rejected = $_.Exception.Message -like '*Inno Setup 7 is required*'
}
if (-not $v6Rejected) { throw 'Inno Setup 6 was not rejected.' }

$defaultSearchRejected = $false
try {
    Resolve-InnoSetup7Compiler -ExplicitPath '' -Candidates @([pscustomobject]@{ Path = $validCompiler; Version = '6.4.0' })
} catch {
    $defaultSearchRejected = $_.Exception.Message -like '*Inno Setup 7 was not found*'
}
if (-not $defaultSearchRejected) { throw 'The installed-candidate search did not reject Inno Setup 6 with an actionable error.' }

$noCompilerMessage = ''
try {
    Resolve-InnoSetup7Compiler -ExplicitPath '' -Candidates @()
} catch {
    $noCompilerMessage = $_.Exception.Message
}
if ($noCompilerMessage -notlike '*winget install --id JRSoftware.InnoSetup.7 -e -s winget -i*' -or
    $noCompilerMessage -notlike '*QUOTATRAY_ISCC*') {
    throw 'The no-compiler error did not provide actionable installation guidance.'
}

Write-Output 'Inno Setup discovery tests: PASS (explicit 7, missing path, reject 6, accept 7, no compiler guidance)'
