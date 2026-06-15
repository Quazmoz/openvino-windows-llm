<#
.SYNOPSIS
    Windows / Python / Intel device preflight for OpenVINO.

.DESCRIPTION
    Reports OS, Python, CPU, GPU, and (best-effort) NPU presence. This is
    informational: OpenVINO can run on CPU almost anywhere, so the script warns
    rather than failing. GPU/NPU acceleration depends on Intel drivers.
#>
[CmdletBinding()]
param([switch]$AllowUnsupported)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Hardware / environment preflight" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# --- OS ---
$os = Get-CimInstance Win32_OperatingSystem
Write-Host ("OS:       {0} (build {1})" -f $os.Caption, $os.BuildNumber)

# --- Python ---
$pythonOk = $false
foreach ($candidate in @("py -3.11", "py -3.12", "python")) {
    $parts = $candidate.Split(" ")
    $exe = $parts[0]
    $rest = if ($parts.Length -gt 1) { $parts[1..($parts.Length - 1)] } else { @() }
    try {
        $ver = & $exe @rest --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host ("Python:   {0}  ({1})" -f $ver, $candidate) -ForegroundColor Green
            $pythonOk = $true
            break
        }
    } catch { }
}
if (-not $pythonOk) {
    Write-Host "Python:   NOT FOUND. Install Python 3.11 or 3.12 from python.org." -ForegroundColor Red
}

# --- CPU ---
$cpu = (Get-CimInstance Win32_Processor | Select-Object -First 1).Name
Write-Host ("CPU:      {0}" -f $cpu)
if ($cpu -match "Ultra") {
    Write-Host "          Intel Core Ultra detected — NPU acceleration may be available." -ForegroundColor Green
}

# --- GPU ---
$gpus = Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name
foreach ($g in $gpus) {
    $color = if ($g -match "Intel") { "Green" } else { "DarkGray" }
    Write-Host ("GPU:      {0}" -f $g) -ForegroundColor $color
}

# --- NPU (best effort) ---
$npu = Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object {
    $_.FriendlyName -match "NPU|AI Boost|Neural"
}
if ($npu) {
    foreach ($n in $npu) {
        Write-Host ("NPU:      {0} [{1}]" -f $n.FriendlyName, $n.Status) -ForegroundColor Green
    }
} else {
    Write-Host "NPU:      not detected via PnP (CPU/GPU will still work)." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Preflight is informational; CPU inference works without GPU/NPU drivers." -ForegroundColor DarkGray
exit 0
