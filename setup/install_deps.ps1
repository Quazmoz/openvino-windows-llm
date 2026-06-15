<#
.SYNOPSIS
    Create the project venv and install Python dependencies.

.PARAMETER WithConvert
    Also install requirements-convert.txt (optimum-intel, nncf).

.PARAMETER Python
    Python launcher (default: "py -3.11", falling back to "py -3.12" then "python").
#>
[CmdletBinding()]
param(
    [switch]$WithConvert,
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvDir = Join-Path $RepoRoot ".venv"

function Resolve-Python {
    param([string]$Preferred)
    $candidates = @()
    if ($Preferred) { $candidates += $Preferred }
    $candidates += @("py -3.11", "py -3.12", "python")
    foreach ($c in $candidates) {
        $parts = $c.Split(" ")
        $exe = $parts[0]
        $rest = if ($parts.Length -gt 1) { $parts[1..($parts.Length - 1)] } else { @() }
        try {
            & $exe @rest --version *> $null
            if ($LASTEXITCODE -eq 0) { return ,@($exe, $rest) }
        } catch { }
    }
    throw "No suitable Python found. Install Python 3.11 or 3.12 from python.org."
}

$py = Resolve-Python -Preferred $Python
$pyExe = $py[0]
$pyRest = $py[1]

if (-not (Test-Path $VenvDir)) {
    Write-Host "Creating virtual environment at $VenvDir ..." -ForegroundColor Cyan
    & $pyExe @pyRest -m venv $VenvDir
} else {
    Write-Host "Using existing virtual environment at $VenvDir" -ForegroundColor DarkGray
}

$venvPython = Join-Path $VenvDir "Scripts\python.exe"

Write-Host "Upgrading pip ..." -ForegroundColor Cyan
& $venvPython -m pip install --upgrade pip

Write-Host "Installing runtime dependencies (requirements.txt) ..." -ForegroundColor Cyan
& $venvPython -m pip install -r (Join-Path $RepoRoot "requirements.txt")

if ($WithConvert) {
    Write-Host "Installing conversion dependencies (requirements-convert.txt) ..." -ForegroundColor Cyan
    & $venvPython -m pip install -r (Join-Path $RepoRoot "requirements-convert.txt")
}

# Mark deps installed so start_server.bat skips re-installing.
"installed" | Out-File -FilePath (Join-Path $RepoRoot ".deps_installed") -Encoding ascii

Write-Host "Dependencies installed." -ForegroundColor Green
& $venvPython -m app.server --check-devices
