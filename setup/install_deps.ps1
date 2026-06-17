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
    try {
        Invoke-Checked -FilePath $pyExe -Arguments ($pyRest + @("-m", "venv", $VenvDir))
    } catch {
        Write-Host "ERROR: Failed to create virtual environment." -ForegroundColor Red
        Write-Host "       Check if you have write access to $RepoRoot or run setup in an Administrator terminal." -ForegroundColor Yellow
        throw $_
    }
} else {
    Write-Host "Using existing virtual environment at $VenvDir" -ForegroundColor DarkGray
}

$venvPython = Join-Path $VenvDir "Scripts\python.exe"

try {
    Write-Host "Upgrading pip ..." -ForegroundColor Cyan
    Invoke-Checked -FilePath $venvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip")

    Write-Host "Installing runtime dependencies (requirements.txt) ..." -ForegroundColor Cyan
    Invoke-Checked -FilePath $venvPython -Arguments @("-m", "pip", "install", "-r", (Join-Path $RepoRoot "requirements.txt"))

    if ($WithConvert) {
        Write-Host "Installing conversion dependencies (requirements-convert.txt) ..." -ForegroundColor Cyan
        Invoke-Checked -FilePath $venvPython -Arguments @("-m", "pip", "install", "-r", (Join-Path $RepoRoot "requirements-convert.txt"))
    }
} catch {
    $errText = $_.Exception.Message
    Write-Host ""
    Write-Host "ERROR: Dependency installation failed." -ForegroundColor Red
    Write-Host "Error details: $errText" -ForegroundColor Red
    Write-Host ""
    Write-Host "--------------------------------------------------" -ForegroundColor Yellow
    Write-Host "             TROUBLESHOOTING DIAGNOSTICS          " -ForegroundColor Yellow
    Write-Host "--------------------------------------------------" -ForegroundColor Yellow

    if ($errText -match "SSL" -or $errText -match "certificate verify failed" -or $errText -match "TLS") {
        Write-Host "[ISSUE] PIP SSL/TLS verification failed (common behind corporate proxies)." -ForegroundColor Yellow
        Write-Host "[FIX]   Try running pip install with trusted hosts manually:" -ForegroundColor Green
        Write-Host "        .\.venv\Scripts\python.exe -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt" -ForegroundColor White
        Write-Host "        Or set the HTTP_PROXY / HTTPS_PROXY environment variables." -ForegroundColor Green
    }
    elseif ($errText -match "PermissionError" -or $errText -match "Access is denied" -or $errText -match "Permission denied") {
        Write-Host "[ISSUE] Access denied. Pip could not write package files." -ForegroundColor Yellow
        Write-Host "[FIX]   Run setup in an Administrator command prompt or PowerShell session." -ForegroundColor Green
    }
    elseif ($errText -match "No space left on device" -or $errText -match "disk space" -or $errText -match "out of space") {
        Write-Host "[ISSUE] Out of disk space." -ForegroundColor Yellow
        Write-Host "[FIX]   Free up space on your installation drive and run setup again." -ForegroundColor Green
    }
    else {
        Write-Host "Generic pip installation failure. Remediation tips:" -ForegroundColor Yellow
        Write-Host " - Run installation manually avoiding pip cache:" -ForegroundColor Gray
        Write-Host "     .\.venv\Scripts\python.exe -m pip install -r requirements.txt --no-cache-dir" -ForegroundColor White
        Write-Host " - Ensure no other Python or server processes are locking venv files." -ForegroundColor Gray
    }
    Write-Host "--------------------------------------------------" -ForegroundColor Yellow
    throw $_
}

# Mark deps installed so start_server.bat skips re-installing.
"installed" | Out-File -FilePath (Join-Path $RepoRoot ".deps_installed") -Encoding ascii

Write-Host "Dependencies installed." -ForegroundColor Green
Invoke-Checked -FilePath $venvPython -Arguments @("-m", "app.server", "--check-devices")
