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
<#
.SYNOPSIS
    Full setup flow for the OpenVINO Windows LLM server.

.DESCRIPTION
    1. Runs hardware / Python preflight checks.
    2. Creates a Python virtual environment and installs runtime dependencies.
    3. Optionally installs the model-conversion dependencies.
    4. Optionally captures a Hugging Face token into .env (for gated models).

.PARAMETER Minimal
    Skip installing requirements-convert.txt (optimum-intel, nncf).

.PARAMETER SkipHardwareCheck
    Skip the hardware/Python preflight.

.PARAMETER Python
    Python launcher to use (default: "py -3.11"; falls back through supported
    launchers, common direct install paths, then "python").
#>
[CmdletBinding()]
param(
    [switch]$Minimal,
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
if (-not $Minimal) { $installArgs["WithConvert"] = $true }
& "$PSScriptRoot\install_deps.ps1" @installArgs

# --- Configure .env if not exists ---
$envFile = Join-Path $RepoRoot ".env"
$envExampleFile = Join-Path $RepoRoot ".env.example"
if (-not (Test-Path $envFile)) {
    if (Test-Path $envExampleFile) {
        Copy-Item -Path $envExampleFile -Destination $envFile
        Write-Host "Created .env from .env.example" -ForegroundColor Green
    }
}

# --- Hugging Face token hint for gated models ---
Write-Host ""
Write-Host "Tip: A Hugging Face token is only needed to convert gated models (e.g., Llama, Gemma)." -ForegroundColor Yellow
Write-Host "     You can configure HF_TOKEN in your .env file." -ForegroundColor Yellow

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  Setup complete." -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Start the server (runs the mock engine by default on first load):" -ForegroundColor Cyan
Write-Host "       .\start_server.bat" -ForegroundColor White
Write-Host "  2. Open the chat UI and prepare models dynamically:  http://localhost:8000" -ForegroundColor Cyan
Write-Host "  3. (Optional) Convert a model manually via terminal:" -ForegroundColor Cyan
Write-Host "       .\setup\convert_model.ps1 -Id tinyllama-1.1b-chat-fp16" -ForegroundColor White
