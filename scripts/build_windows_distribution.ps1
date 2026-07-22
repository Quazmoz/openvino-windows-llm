[CmdletBinding()]
param(
    [string]$Version = "",
    [string]$Python = "python",
    [string]$IsccPath = $env:ISCC_PATH,
    [switch]$SkipInstaller,
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

if (-not $Version) {
    $Version = & $Python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"
}
if ($Version -notmatch '^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$') {
    throw "Invalid application version: $Version"
}

$Dist = Join-Path $Root "dist"
$Build = Join-Path $Root "build"
$Artifacts = Join-Path $Root "artifacts"
Remove-Item $Dist, $Build -Recurse -Force -ErrorAction SilentlyContinue
New-Item $Artifacts -ItemType Directory -Force | Out-Null

if (-not $SkipDependencyInstall) {
    & $Python -m pip install --upgrade pip
    & $Python -m pip install ".[convert,distribution]"
}

$ThirdParty = Join-Path ([IO.Path]::GetTempPath()) ("ovllm-third-party-" + [guid]::NewGuid().ToString("N") + ".txt")
$env:OV_LLM_THIRD_PARTY_NOTICES = $ThirdParty
& $Python -m piplicenses --format=plain-vertical --with-license-file --output-file=$ThirdParty
& $Python -m PyInstaller --noconfirm --clean packaging/openvino_windows_llm.spec

$BuiltRoot = Join-Path $Dist "OpenVINOWindowsLLM"
$Exe = Join-Path $BuiltRoot "OpenVINOWindowsLLM.exe"
if (-not (Test-Path $Exe)) { throw "Packaged executable was not produced: $Exe" }

$Signed = $false
if ($env:OV_LLM_SIGNTOOL_PATH -and $env:OV_LLM_SIGN_CERT_SHA1) {
    $Timestamp = if ($env:OV_LLM_SIGN_TIMESTAMP_URL) { $env:OV_LLM_SIGN_TIMESTAMP_URL } else { "http://timestamp.digicert.com" }
    & $env:OV_LLM_SIGNTOOL_PATH sign /sha1 $env:OV_LLM_SIGN_CERT_SHA1 /fd SHA256 /tr $Timestamp /td SHA256 $Exe
    $Signed = $true
}
$Suffix = if ($Signed) { "signed" } else { "unsigned" }

$PortableStage = Join-Path $Build "portable\OpenVINOWindowsLLM"
New-Item $PortableStage -ItemType Directory -Force | Out-Null
Copy-Item (Join-Path $BuiltRoot "*") $PortableStage -Recurse -Force
Set-Content -Path (Join-Path $PortableStage "portable.flag") -Value "portable" -Encoding ascii
$PortableZip = Join-Path $Artifacts "OpenVINOWindowsLLM-$Version-windows-x64-portable-$Suffix.zip"
Remove-Item $PortableZip -Force -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path (Split-Path $PortableStage -Parent) "OpenVINOWindowsLLM") -DestinationPath $PortableZip -CompressionLevel Optimal

$Installer = $null
if (-not $SkipInstaller) {
    if (-not $IsccPath) {
        $Candidates = @(
            "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
            "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
            "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
        )
        $IsccPath = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    }
    if (-not $IsccPath -or -not (Test-Path $IsccPath)) {
        throw "Inno Setup 6 compiler was not found. Set ISCC_PATH or use -SkipInstaller."
    }
    & $IsccPath "/DMyAppVersion=$Version" "/DSourceRoot=$BuiltRoot" "/DArtifactDir=$Artifacts" "/DArtifactSuffix=$Suffix" packaging/installer.iss
    $Installer = Join-Path $Artifacts "OpenVINOWindowsLLM-$Version-windows-x64-setup-$Suffix.exe"
    if (-not (Test-Path $Installer)) { throw "Installer was not produced: $Installer" }
    if ($Signed) {
        $Timestamp = if ($env:OV_LLM_SIGN_TIMESTAMP_URL) { $env:OV_LLM_SIGN_TIMESTAMP_URL } else { "http://timestamp.digicert.com" }
        & $env:OV_LLM_SIGNTOOL_PATH sign /sha1 $env:OV_LLM_SIGN_CERT_SHA1 /fd SHA256 /tr $Timestamp /td SHA256 $Installer
    }
}

$Outputs = @($PortableZip)
if ($Installer) { $Outputs += $Installer }
$ChecksumFile = Join-Path $Artifacts "OpenVINOWindowsLLM-$Version-SHA256SUMS.txt"
$Lines = foreach ($Path in $Outputs) {
    $Hash = Get-FileHash -Path $Path -Algorithm SHA256
    "$($Hash.Hash.ToLowerInvariant())  $([IO.Path]::GetFileName($Path))"
}
Set-Content -Path $ChecksumFile -Value $Lines -Encoding ascii

Write-Host "Built artifacts:"
$Outputs + $ChecksumFile | ForEach-Object { Write-Host "  $_" }
if (-not $Signed) { Write-Warning "Artifacts are unsigned development builds." }
Remove-Item $ThirdParty -Force -ErrorAction SilentlyContinue
Remove-Item Env:OV_LLM_THIRD_PARTY_NOTICES -ErrorAction SilentlyContinue
