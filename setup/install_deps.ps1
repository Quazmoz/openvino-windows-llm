<#
.SYNOPSIS
    Create the project venv and install Python dependencies.

.PARAMETER WithConvert
    Also install requirements-convert.txt (optimum-intel, nncf).

.PARAMETER Python
    Python launcher (default: "py -3.11", falling back through newer supported
    launchers, common direct install paths, then "python").
#>
[CmdletBinding()]
param(
    [switch]$WithConvert,
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvDir = Join-Path $RepoRoot ".venv"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [string[]]$Arguments = @()
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        $cmd = @($FilePath) + $Arguments
        throw "Command failed with exit code $LASTEXITCODE`: $($cmd -join ' ')"
    }
}

function Resolve-Python {
    param([string]$Preferred)
    $candidates = @()
    if ($Preferred) { $candidates += $Preferred }
    $candidates += @(
        "py -3.11",
        "py -3.12",
        "py -3.13",
        "$env:LOCALAPPDATA\Python\pythoncore-3.11-64\python.exe",
        "$env:LOCALAPPDATA\Python\pythoncore-3.12-64\python.exe",
        "$env:LOCALAPPDATA\Python\pythoncore-3.13-64\python.exe"
    )
    $installRoots = @(
        "$env:LOCALAPPDATA\Python",
        "C:\Program Files"
    )
    foreach ($root in $installRoots) {
        $candidates += Get-ChildItem -Path $root -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match "^(Python|pythoncore)-3\.(11|12|13)" } |
            Sort-Object FullName |
            ForEach-Object { Join-Path $_.FullName "python.exe" }
    }
    $candidates += "python"

    foreach ($c in $candidates) {
        if (-not $c) { continue }
        if (Test-Path $c) {
            $exe = $c
            $rest = @()
        } else {
            $parts = $c.Split(" ", 2)
            $exe = $parts[0]
            $rest = if ($parts.Length -gt 1) { $parts[1..($parts.Length - 1)] } else { @() }
        }
        try {
            & $exe @rest --version *> $null
            if ($LASTEXITCODE -eq 0) { return ,@($exe, $rest) }
        } catch { }
    }
    throw "No suitable Python found. Install Python 3.11, 3.12, or 3.13 from python.org, or pass -Python with the full python.exe path."
}

$py = Resolve-Python -Preferred $Python
$pyExe = $py[0]
$pyRest = $py[1]

if (-not (Test-Path $VenvDir)) {
    Write-Host "Creating virtual environment at $VenvDir ..." -ForegroundColor Cyan
    Invoke-Checked -FilePath $pyExe -Arguments ($pyRest + @("-m", "venv", $VenvDir))
} else {
    Write-Host "Using existing virtual environment at $VenvDir" -ForegroundColor DarkGray
}

$venvPython = Join-Path $VenvDir "Scripts\python.exe"

Write-Host "Upgrading pip ..." -ForegroundColor Cyan
Invoke-Checked -FilePath $venvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip")

Write-Host "Installing runtime dependencies (requirements.txt) ..." -ForegroundColor Cyan
Invoke-Checked -FilePath $venvPython -Arguments @("-m", "pip", "install", "-r", (Join-Path $RepoRoot "requirements.txt"))

if ($WithConvert) {
    Write-Host "Installing conversion dependencies (requirements-convert.txt) ..." -ForegroundColor Cyan
    Invoke-Checked -FilePath $venvPython -Arguments @("-m", "pip", "install", "-r", (Join-Path $RepoRoot "requirements-convert.txt"))
}

# Mark deps installed so start_server.bat skips re-installing.
"installed" | Out-File -FilePath (Join-Path $RepoRoot ".deps_installed") -Encoding ascii

Write-Host "Dependencies installed." -ForegroundColor Green
Invoke-Checked -FilePath $venvPython -Arguments @("-m", "app.server", "--check-devices")
