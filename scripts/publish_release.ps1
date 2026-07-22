[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Version,
    [ValidateSet("stable", "beta", "nightly")][string]$Channel = "stable",
    [string]$ArtifactDirectory = "",
    [switch]$DryRun,
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root
if (-not $ArtifactDirectory) { $ArtifactDirectory = Join-Path $Root "artifacts\release-$Version" }
$ArtifactDirectory = (Resolve-Path $ArtifactDirectory).Path

& $Python scripts/release_tools.py validate-version --version $Version --channel $Channel
if ($LASTEXITCODE -ne 0) { throw "Invalid version or channel." }
& $Python scripts/release_tools.py verify-version-consistency --root $Root --version $Version
if ($LASTEXITCODE -ne 0) { throw "Version consistency check failed." }
if (-not [string]::IsNullOrWhiteSpace((git status --porcelain))) { throw "Publishing requires a clean working tree." }

$Tag = "v$Version"
$Expected = @(
    "OpenVINO-Windows-LLM-$Version-windows-x64-installer.exe",
    "OpenVINO-Windows-LLM-$Version-windows-x64-portable.zip",
    "OpenVINO-Windows-LLM-$Version-checksums.txt",
    "OpenVINO-Windows-LLM-$Version-release-manifest.json",
    "OpenVINO-Windows-LLM-$Version-third-party-licenses.zip",
    "OpenVINO-Windows-LLM-$Version-release-notes.md"
)
$Existing = Get-ChildItem $ArtifactDirectory -File | Select-Object -ExpandProperty Name
foreach ($Name in $Expected) {
    if ($Existing -notcontains $Name) { throw "Missing release artifact: $Name" }
}
& $Python scripts/release_tools.py verify-checksums --path (Join-Path $ArtifactDirectory "OpenVINO-Windows-LLM-$Version-checksums.txt")
if ($LASTEXITCODE -ne 0) { throw "Checksum verification failed." }

& git rev-parse --verify --quiet "refs/tags/$Tag" | Out-Null
if ($LASTEXITCODE -eq 0) { throw "Tag $Tag already exists." }
& gh release view $Tag --repo Quazmoz/openvino-windows-llm 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) { throw "GitHub release $Tag already exists." }

$Notes = Join-Path $ArtifactDirectory "OpenVINO-Windows-LLM-$Version-release-notes.md"
$Upload = $Expected | ForEach-Object { Join-Path $ArtifactDirectory $_ }
if ($DryRun) {
    Write-Host "Dry run passed. Would create annotated tag $Tag and upload:"
    $Upload | ForEach-Object { Write-Host "  $_" }
    exit 0
}

git tag -a $Tag -m "OpenVINO Windows LLM $Version"
if ($LASTEXITCODE -ne 0) { throw "Annotated tag creation failed." }
git push origin $Tag
if ($LASTEXITCODE -ne 0) { throw "Tag push failed." }

$Arguments = @("release", "create", $Tag, "--repo", "Quazmoz/openvino-windows-llm", "--verify-tag", "--title", "OpenVINO Windows LLM $Version", "--notes-file", $Notes)
if ($Channel -ne "stable") { $Arguments += "--prerelease" }
$Arguments += $Upload
& gh @Arguments
if ($LASTEXITCODE -ne 0) { throw "GitHub release creation or upload failed." }
$AssetJson = & gh release view $Tag --repo Quazmoz/openvino-windows-llm --json assets
if ($LASTEXITCODE -ne 0) { throw "Published release could not be re-read for artifact verification." }
$PublishedNames = @((($AssetJson | ConvertFrom-Json).assets) | ForEach-Object { $_.name })
foreach ($Name in $Expected) {
    if ($PublishedNames -notcontains $Name) { throw "Published release is missing artifact: $Name" }
}
Write-Host "Published and verified GitHub release $Tag."
