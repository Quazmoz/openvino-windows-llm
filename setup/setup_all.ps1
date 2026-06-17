<#
.SYNOPSIS
    Full setup flow for the OpenVINO Windows LLM server.

.DESCRIPTION
    1. Runs hardware / Python preflight checks.
    2. Creates a Python virtual environment and installs runtime dependencies.
    3. Optionally installs the model-conversion dependencies.
    4. Optionally captures a Hugging Face token into .env (for gated models).

.PARAMETER WithConvert
    Also install requirements-convert.txt (optimum-intel, nncf) for model export.

.PARAMETER SkipHardwareCheck
    Skip the hardware/Python preflight.

.PARAMETER Python
    Python launcher to use (default: "py -3.11"; falls back through supported
    launchers, common direct install paths, then "python").
#>
[CmdletBinding()]
param(
    [switch]$WithConvert,
    [switch]$SkipHardwareCheck,
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "Repo: $RepoRoot" -ForegroundColor DarkGray

if (-not $SkipHardwareCheck) {
    & "$PSScriptRoot\check_hardware.ps1"
    Write-Host ""
}

$installArgs = @{ Python = $Python }
if ($WithConvert) { $installArgs["WithConvert"] = $true }
& "$PSScriptRoot\install_deps.ps1" @installArgs

# --- Optional Hugging Face token (only needed to convert gated models) ---
$envFile = Join-Path $RepoRoot ".env"
if (-not (Test-Path $envFile)) {
    Write-Host ""
    Write-Host "A Hugging Face token is only needed to convert GATED models (e.g. Llama)." -ForegroundColor Yellow
    $token = Read-Host "Paste an HF token to save to .env, or press Enter to skip"
    if ($token.Trim().Length -gt 0) {
        "HF_TOKEN=$($token.Trim())" | Out-File -FilePath $envFile -Encoding utf8
        Write-Host "Saved token to .env" -ForegroundColor Green
    } else {
        Write-Host "Skipped. You can copy .env.example to .env later." -ForegroundColor DarkGray
    }
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  Setup complete." -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Convert a small model to OpenVINO IR:" -ForegroundColor Cyan
Write-Host "       .\setup\convert_model.ps1 -Id tinyllama-1.1b-chat-fp16" -ForegroundColor White
Write-Host "  2. Start the server:" -ForegroundColor Cyan
Write-Host "       .\start_server.bat --model tinyllama-1.1b-chat-fp16 --device NPU" -ForegroundColor White
Write-Host "  3. Open the chat UI:  http://localhost:8000" -ForegroundColor Cyan
