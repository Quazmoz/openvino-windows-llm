[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$DistributionPath,
    [string]$Python = "python",
    [int]$HeadlessSeconds = 120
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Root = (Resolve-Path $DistributionPath).Path
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Exe = Join-Path $Root "OpenVINOWindowsLLM.exe"
if (-not (Test-Path $Exe)) { throw "Executable not found: $Exe" }
$Data = Join-Path ([IO.Path]::GetTempPath()) ("OV LLM Packaged Smoke " + [guid]::NewGuid().ToString("N"))
New-Item $Data -ItemType Directory -Force | Out-Null
$Process = $null

try {
    $Process = Start-Process -FilePath $Exe -ArgumentList @(
        "--mock", "--headless", "--headless-seconds", "$HeadlessSeconds",
        "--portable", "--data-dir", ('"' + $Data + '"'), "--no-browser"
    ) -WorkingDirectory $Root -PassThru -WindowStyle Hidden

    $MetadataPath = Join-Path $Data "desktop-instance.json"
    $Deadline = [DateTime]::UtcNow.AddSeconds(90)
    do {
        if ($Process.HasExited) { throw "Packaged tray exited with code $($Process.ExitCode)." }
        Start-Sleep -Milliseconds 300
    } until ((Test-Path $MetadataPath) -or [DateTime]::UtcNow -gt $Deadline)
    if (-not (Test-Path $MetadataPath)) { throw "Packaged tray did not publish server metadata." }

    $Metadata = Get-Content -Raw $MetadataPath | ConvertFrom-Json
    $Origin = "http://127.0.0.1:$($Metadata.port)"
    $Deadline = [DateTime]::UtcNow.AddSeconds(90)
    do {
        if ($Process.HasExited) { throw "Packaged tray exited with code $($Process.ExitCode)." }
        Start-Sleep -Milliseconds 300
        try { $Ready = Invoke-RestMethod "$Origin/health/ready" -TimeoutSec 3 } catch { $Ready = $null }
    } until (($Ready.status -eq "ready") -or [DateTime]::UtcNow -gt $Deadline)
    if ($Ready.status -ne "ready") { throw "Packaged server did not become ready." }

    $Instance = Invoke-RestMethod "$Origin/desktop/instance" -TimeoutSec 10
    if ($Instance.instance_nonce -ne $Metadata.nonce) { throw "Packaged desktop identity did not match tray metadata." }
    $Release = Invoke-RestMethod "$Origin/desktop/release/status" -TimeoutSec 10
    if (-not $Release.build.application_version) { throw "Packaged release metadata is missing." }
    $Ui = Invoke-WebRequest -UseBasicParsing -Uri "$Origin/" -TimeoutSec 20
    if ($Ui.Content -notmatch "About & Updates") { throw "Packaged About and Updates UI is missing." }

    $ValidatorArguments = @(
        (Join-Path $RepoRoot "scripts\validate_api_contract.py"),
        "--base-url", $Origin,
        "--profile", "full",
        "--model", "tinyllama-1.1b-chat-fp16",
        "--device", "CPU",
        "--expect-mock",
        "--include-embeddings",
        "--run-benchmark",
        "--exercise-lifecycle"
    )
    & $Python @ValidatorArguments
    if ($LASTEXITCODE -ne 0) { throw "Packaged external API contract validation failed." }

    @{ command = "quit"; created_at = [DateTime]::UtcNow.ToString("o") } |
        ConvertTo-Json | Set-Content -Path (Join-Path $Data "tray-command.json") -Encoding utf8
    if (-not $Process.WaitForExit(20000)) { throw "Packaged tray did not shut down after the owned quit command." }
    if ($Process.ExitCode -ne 0) { throw "Packaged tray exited with code $($Process.ExitCode)." }
    Write-Host "Packaged tray-owned mock smoke test passed."
}
finally {
    if ($Process -and -not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        $Process.WaitForExit(10000) | Out-Null
    }
    Remove-Item $Data -Recurse -Force -ErrorAction SilentlyContinue
}
