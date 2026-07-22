[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$DistributionPath,
    [int]$Port = 8123
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path $DistributionPath).Path
$Exe = Join-Path $Root "OpenVINOWindowsLLM.exe"
if (-not (Test-Path $Exe)) { throw "Executable not found: $Exe" }
$Data = Join-Path ([IO.Path]::GetTempPath()) ("ovllm-smoke-" + [guid]::NewGuid().ToString("N"))
New-Item $Data -ItemType Directory -Force | Out-Null
$Nonce = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes([guid]::NewGuid().ToString("N")))
$Process = Start-Process -FilePath $Exe -ArgumentList @("--server-child", "--port", $Port, "--instance-nonce", $Nonce, "--portable", "--data-dir", $Data, "--mock") -PassThru -WindowStyle Hidden

function Invoke-Json([string]$Method, [string]$Uri, [object]$Body = $null, [hashtable]$Headers = @{}) {
    $Arguments = @{ Method = $Method; Uri = $Uri; Headers = $Headers; TimeoutSec = 20 }
    if ($null -ne $Body) { $Arguments.Body = ($Body | ConvertTo-Json -Depth 12); $Arguments.ContentType = "application/json" }
    Invoke-RestMethod @Arguments
}

try {
    $Origin = "http://127.0.0.1:$Port"
    $Deadline = (Get-Date).AddSeconds(90)
    do {
        Start-Sleep -Milliseconds 300
        try { $Ready = Invoke-Json GET "$Origin/health/ready" } catch { $Ready = $null }
    } until (($Ready.status -eq "ready") -or ((Get-Date) -gt $Deadline) -or $Process.HasExited)
    if ($Process.HasExited) { throw "Packaged server exited with code $($Process.ExitCode)" }
    if ($Ready.status -ne "ready") { throw "Packaged server did not become ready" }

    $Instance = Invoke-Json GET "$Origin/desktop/instance"
    if ($Instance.instance_nonce -ne $Nonce) { throw "Desktop instance identity mismatch" }
    $null = Invoke-WebRequest -UseBasicParsing -Uri "$Origin/" -TimeoutSec 20
    $Status = Invoke-Json GET "$Origin/v1/onboarding/status"
    $Scan = Invoke-Json GET "$Origin/v1/onboarding/system-scan"
    $Recommendation = Invoke-Json GET "$Origin/v1/onboarding/recommendation"
    if (-not $Recommendation.model_id) { throw "Mock recommendation missing" }

    $PrepareBody = @{
        model_id = $Recommendation.model_id
        device = $Recommendation.requested_device
        confirm_license = $true
        confirm_disk_requirement = $true
        acknowledge_warnings = $true
        trust_remote_code = $false
    }
    $Job = Invoke-Json POST "$Origin/v1/onboarding/prepare" $PrepareBody
    $Deadline = (Get-Date).AddSeconds(90)
    do {
        Start-Sleep -Milliseconds 250
        $Job = Invoke-Json GET "$Origin/v1/onboarding/preparation/$($Job.job_id)"
    } until (($Job.status -ne "running") -or ((Get-Date) -gt $Deadline))
    if ($Job.status -ne "ready") { throw "Mock onboarding failed: $($Job.error_detail)" }

    $Models = Invoke-Json GET "$Origin/v1/models"
    $Chat = Invoke-Json POST "$Origin/v1/chat/completions" @{ model = $Recommendation.model_id; messages = @(@{ role = "user"; content = "smoke test" }); stream = $false; max_tokens = 8 }
    $Response = Invoke-Json POST "$Origin/v1/responses" @{ model = $Recommendation.model_id; input = "smoke test"; stream = $false; max_output_tokens = 8 }
    $Stream = Invoke-WebRequest -UseBasicParsing -Method POST -Uri "$Origin/v1/chat/completions" -ContentType "application/json" -Body (@{ model = $Recommendation.model_id; messages = @(@{ role = "user"; content = "stream" }); stream = $true; max_tokens = 8 } | ConvertTo-Json -Depth 8)
    if ($Stream.Content -notmatch '\[DONE\]') { throw "Streaming completion did not finish" }

    Invoke-Json POST "$Origin/desktop/shutdown" $null @{ "X-Instance-Nonce" = $Nonce } | Out-Null
    if (-not $Process.WaitForExit(15000)) { throw "Packaged server did not shut down cleanly" }
    if ($Process.ExitCode -ne 0) { throw "Packaged server exited with code $($Process.ExitCode)" }
    Write-Host "Packaged mock smoke test passed."
}
finally {
    if (-not $Process.HasExited) { Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue }
    Remove-Item $Data -Recurse -Force -ErrorAction SilentlyContinue
}
