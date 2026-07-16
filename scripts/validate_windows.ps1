[CmdletBinding()]
param(
    [string]$Model = "tinyllama-1.1b-chat-fp16",
    [string[]]$Devices = @("CPU", "GPU", "NPU", "AUTO"),
    [string]$EmbeddingModel = "bge-small-en-v1.5",
    [switch]$IncludeEmbeddings,
    [switch]$SkipConversion,
    [switch]$ContinueOnFailure,
    [switch]$KeepServerLogs,
    [string]$ApiKey = "",
    [string]$OutputDirectory = "certification/results",
    [int]$Port = 8765,
    [int]$LoadTimeoutSeconds = 900,
    [int]$RequestTimeoutSeconds = 120
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Test-Windows {
    if (Get-Variable IsWindows -ErrorAction SilentlyContinue) { return [bool]$IsWindows }
    return $env:OS -eq "Windows_NT"
}

function Get-Python([string]$Root) {
    $venv = Join-Path $Root ".venv\Scripts\python.exe"
    if (Test-Path $venv) { return $venv }
    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    throw "Python was not found. Run .\setup.bat first."
}

function Stop-Server([AllowNull()][System.Diagnostics.Process]$Process) {
    if ($Process -and -not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        $Process.WaitForExit(10000) | Out-Null
    }
}

function Wait-Health(
    [string]$BaseUrl,
    [System.Diagnostics.Process]$Process,
    [int]$TimeoutSeconds
) {
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($Process.HasExited) { throw "Server exited with code $($Process.ExitCode)." }
        try {
            $health = Invoke-RestMethod "$BaseUrl/health" -TimeoutSec 5
            if ($health.status -in @("ok", "busy")) { return }
        }
        catch { Start-Sleep 1 }
    }
    throw "Timed out waiting for $BaseUrl/health."
}

function Safe-Text([string]$Text, [string]$Secret) {
    if (-not $Text) { return "" }
    if ($Secret) { $Text = $Text.Replace($Secret, "[redacted]") }
    $Text = [regex]::Replace($Text, "(?i)Bearer\s+\S+|hf_[A-Za-z0-9_=-]{8,}", "[redacted]")
    return [regex]::Replace($Text, "[A-Za-z]:\\[^`r`n]+", "[local-path]")
}

function Python-Json([string]$Python, [string]$Code) {
    $output = & $Python -c $Code 2>&1
    if ($LASTEXITCODE -ne 0) { throw ($output -join [Environment]::NewLine) }
    return ($output -join [Environment]::NewLine) | ConvertFrom-Json
}

if (-not (Test-Windows)) { throw "This harness must run on Windows." }

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $root
$server = $null
$oldKey = $env:OV_LLM_API_KEY
$oldMock = $env:OV_LLM_MOCK
$oldAuto = $env:OV_LLM_AUTO_CONVERT

try {
    $python = Get-Python $root
    $validator = Join-Path $root "scripts\validate_api_contract.py"
    if (-not (Test-Path $validator)) { throw "Missing $validator" }

    $outputRoot = if ([IO.Path]::IsPathRooted($OutputDirectory)) {
        $OutputDirectory
    } else {
        Join-Path $root $OutputDirectory
    }
    $stamp = [DateTime]::UtcNow.ToString("yyyyMMdd-HHmmss")
    $session = Join-Path $outputRoot "windows-certification-$stamp"
    New-Item -ItemType Directory -Path $session -Force | Out-Null

    $deviceCode = @'
import json
from runtime import device_check
available = device_check.available_devices()
print(json.dumps({
    "openvino": device_check.is_openvino_available(),
    "available": available,
    "details": device_check.device_details(),
}))
'@
    $discovery = Python-Json $python $deviceCode
    if (-not $discovery.openvino) { throw "OpenVINO is not available in this environment." }
    $available = @($discovery.available)
    if ($available.Count -eq 0) { throw "OpenVINO reported no devices." }

    $packageCode = @'
import importlib.metadata as metadata
import json
names = ["openvino", "openvino-genai", "optimum-intel", "nncf", "fastapi", "pydantic"]
versions = {}
for name in names:
    try:
        versions[name] = metadata.version(name)
    except metadata.PackageNotFoundError:
        versions[name] = None
print(json.dumps(versions))
'@
    $packages = Python-Json $python $packageCode
    $os = Get-CimInstance Win32_OperatingSystem
    $computer = Get-CimInstance Win32_ComputerSystem
    $machine = [ordered]@{
        os = "$($os.Caption) $($os.Version) build $($os.BuildNumber)"
        architecture = $os.OSArchitecture
        memory_gb = [Math]::Round($computer.TotalPhysicalMemory / 1GB, 2)
        processors = @(Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name)
        video_controllers = @(Get-CimInstance Win32_VideoController | ForEach-Object {
            [ordered]@{ name = $_.Name; driver_version = $_.DriverVersion }
        })
        python = (& $python --version 2>&1) -join " "
        packages = $packages
    }

    $results = @()
    $embeddingPending = [bool]$IncludeEmbeddings
    foreach ($rawDevice in $Devices) {
        $device = $rawDevice.Trim().ToUpperInvariant()
        if (-not $device) { continue }
        if ($device -in @("CPU", "GPU", "NPU") -and $device -notin $available) {
            $results += [ordered]@{
                device = $device
                status = "skipped"
                reason = "OpenVINO did not report this device."
                summary = [ordered]@{ pass = 0; warn = 0; skip = 1; fail = 0 }
            }
            continue
        }

        $slug = ($device -replace "[^A-Z0-9]+", "-").Trim("-").ToLowerInvariant()
        $stdout = Join-Path $session "server-$slug.stdout.log"
        $stderr = Join-Path $session "server-$slug.stderr.log"
        $jsonReport = Join-Path $session "api-$slug.json"
        $mdReport = Join-Path $session "api-$slug.md"
        $baseUrl = "http://127.0.0.1:$Port"

        $env:OV_LLM_API_KEY = $ApiKey
        $env:OV_LLM_MOCK = ""
        $env:OV_LLM_AUTO_CONVERT = if ($SkipConversion) { "" } else { "1" }
        $serverArgs = @(
            "-m", "app.server", "--host", "127.0.0.1", "--port", "$Port",
            "--model", $Model, "--device", $device
        )
        if (-not $SkipConversion) { $serverArgs += "--auto-convert" }

        Write-Host "Validating $Model on $device..."
        $start = @{
            FilePath = $python
            ArgumentList = $serverArgs
            WorkingDirectory = $root
            RedirectStandardOutput = $stdout
            RedirectStandardError = $stderr
            PassThru = $true
            WindowStyle = "Hidden"
        }
        $server = Start-Process @start

        $stopAfterDevice = $false
        try {
            Wait-Health $baseUrl $server 60
            $validatorArgs = @(
                $validator, "--base-url", $baseUrl, "--profile", "full",
                "--model", $Model, "--device", $device, "--expect-real",
                "--run-benchmark", "--exercise-lifecycle",
                "--timeout", "$RequestTimeoutSeconds",
                "--load-timeout", "$LoadTimeoutSeconds",
                "--output-json", $jsonReport, "--output-markdown", $mdReport
            )
            if ($ApiKey) { $validatorArgs += @("--api-key", $ApiKey) }
            if ($embeddingPending) {
                $validatorArgs += @("--include-embeddings", "--embedding-model", $EmbeddingModel)
            }
            & $python @validatorArgs
            $exitCode = $LASTEXITCODE
            $api = Get-Content -Raw $jsonReport | ConvertFrom-Json
            $status = if ($exitCode -eq 0 -and $api.summary.fail -eq 0) { "passed" } else { "failed" }
            $results += [ordered]@{
                device = $device
                status = $status
                reason = ""
                summary = $api.summary
                report = Split-Path -Leaf $mdReport
            }
            $embeddingPending = $false
            if ($status -eq "failed" -and -not $ContinueOnFailure) {
                $stopAfterDevice = $true
            }
        }
        catch {
            if (-not (Test-Path $jsonReport)) {
                $results += [ordered]@{
                    device = $device
                    status = "failed"
                    reason = Safe-Text $_.Exception.Message $ApiKey
                    summary = [ordered]@{ pass = 0; warn = 0; skip = 0; fail = 1 }
                }
            }
            if (-not $ContinueOnFailure) { $stopAfterDevice = $true }
            Write-Warning $_.Exception.Message
        }
        finally {
            Stop-Server $server
            $server = $null
            if (-not $KeepServerLogs) {
                Remove-Item $stdout, $stderr -Force -ErrorAction SilentlyContinue
            }
        }
        if ($stopAfterDevice) { break }
    }

    $summary = [ordered]@{
        passed = @($results | Where-Object status -eq "passed").Count
        skipped = @($results | Where-Object status -eq "skipped").Count
        failed = @($results | Where-Object status -eq "failed").Count
    }
    $report = [ordered]@{
        schema_version = 1
        generated_at = [DateTime]::UtcNow.ToString("o")
        model = $Model
        embedding_model = if ($IncludeEmbeddings) { $EmbeddingModel } else { $null }
        requested_devices = @($Devices)
        detected_devices = $available
        device_details = $discovery.details
        machine = $machine
        summary = $summary
        device_results = $results
    }
    $jsonPath = Join-Path $session "windows-certification.json"
    $mdPath = Join-Path $session "windows-certification.md"
    $report | ConvertTo-Json -Depth 12 | Set-Content $jsonPath -Encoding UTF8

    $lines = @(
        "# OpenVINO Windows Hardware Certification", "",
        "- Generated: ``$($report.generated_at)``",
        "- Model: ``$Model``",
        "- Detected devices: ``$($available -join ', ')``", "",
        "**Result:** $($summary.passed) passed, $($summary.skipped) skipped, $($summary.failed) failed.", "",
        "| Device | Status | Passed | Warnings | Skipped | Failed |",
        "|---|---:|---:|---:|---:|---:|"
    )
    foreach ($result in $results) {
        $lines += "| $($result.device) | **$($result.status.ToUpperInvariant())** | $($result.summary.pass) | $($result.summary.warn) | $($result.summary.skip) | $($result.summary.fail) |"
    }
    $lines += @(
        "", "> Reports exclude API keys, prompts, generated text, hostnames, usernames, serial numbers, and full local paths.", ""
    )
    Set-Content $mdPath ($lines -join [Environment]::NewLine) -Encoding UTF8
    Write-Host "Certification report: $mdPath"
    if ($summary.failed -gt 0) { exit 1 }
}
finally {
    Stop-Server $server
    $env:OV_LLM_API_KEY = $oldKey
    $env:OV_LLM_MOCK = $oldMock
    $env:OV_LLM_AUTO_CONVERT = $oldAuto
    Pop-Location
}
