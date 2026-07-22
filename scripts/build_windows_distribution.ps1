[CmdletBinding()]
param(
    [string]$Version = "",
    [string]$Python = "python",
    [string]$IsccPath = $env:ISCC_PATH,
    [switch]$SkipInstaller,
    [switch]$SkipDependencyInstall
)

if ($SkipDependencyInstall) {
    throw "-SkipDependencyInstall is no longer supported for production builds. The release command always creates an isolated pinned environment."
}
$Arguments = @{
    Version = $Version
    Channel = "stable"
    Python = $Python
    IsccPath = $IsccPath
    Clean = $true
    Unsigned = $true
    MockSmokeTest = $true
    GenerateChecksums = $true
}
if ($SkipInstaller) { $Arguments.SkipInstaller = $true }
& (Join-Path $PSScriptRoot "build_release.ps1") @Arguments
exit $LASTEXITCODE
