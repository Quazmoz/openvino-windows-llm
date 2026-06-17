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
# Candidates list, prioritizing specific versions, default launcher, then python
$candidates = @("py -3.14", "py -3.13", "py -3.12", "py -3.11", "py", "python")

foreach ($candidate in $candidates) {
    $parts = $candidate.Split(" ")
    $exe = $parts[0]
    
    # Skip Microsoft Store dummy python aliases because they hang non-interactive sessions
    if ($exe -match "^python") {
        $resolved = Get-Command $exe -ErrorAction SilentlyContinue
        if ($resolved -and $resolved.Source -match "Microsoft\\WindowsApps") {
            continue
        }
    }

    try {
        if ($parts.Length -gt 1) {
            $arg = $parts[1]
            $ver = & $exe $arg --version 2>&1
        } else {
            $ver = & $exe --version 2>&1
        }
        if ($LASTEXITCODE -eq 0) {
            Write-Host ("Python:   {0}  ({1})" -f $ver, $candidate) -ForegroundColor Green
            $pythonOk = $true
            break
        }
    } catch { }
}
if (-not $pythonOk) {
    Write-Host "Python:   NOT FOUND. Install Python 3.11, 3.12, 3.13 or 3.14 from python.org." -ForegroundColor Red
}

# --- CPU ---
$cpu = (Get-CimInstance Win32_Processor | Select-Object -First 1).Name
Write-Host ("CPU:      {0}" -f $cpu)
if ($cpu -match "Ultra") {
    Write-Host "          Intel Core Ultra detected - NPU acceleration may be available." -ForegroundColor Green
}

# --- GPU ---
$gpus = Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name
foreach ($g in $gpus) {
    $color = if ($g -match "Intel") { "Green" } else { "DarkGray" }
    Write-Host ("GPU:      {0}" -f $g) -ForegroundColor $color
}

# --- NPU (best effort) ---
$npu = Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object {
    $_.FriendlyName -match "\bNPU\b|AI Boost|Neural"
}
if ($npu) {
    foreach ($n in $npu) {
        Write-Host ("NPU:      {0} [{1}]" -f $n.FriendlyName, $n.Status) -ForegroundColor Green
        
        # Try to query the signed driver version
        try {
            $driver = Get-CimInstance -ClassName Win32_PnPSignedDriver -ErrorAction SilentlyContinue | Where-Object {
                $_.DeviceID -eq $n.DeviceId
            }
            if ($driver) {
                $ver = $driver.DriverVersion
                $date = $driver.DriverDate
                Write-Host ("          Driver version: {0} ({1})" -f $ver, $date) -ForegroundColor Green
                
                # Check for minimum recommended driver version (32.0.100.3104)
                if ($ver -match "^(\d+)\.(\d+)\.(\d+)\.(\d+)") {
                    $major = [int]$Matches[1]
                    $minor = [int]$Matches[2]
                    $build1 = [int]$Matches[3]
                    $build2 = [int]$Matches[4]
                    
                    # 32.0.100.3104: major=32, minor=0, build1=100, build2=3104
                    $isOutdated = $false
                    if ($major -lt 32) { $isOutdated = $true }
                    elseif ($major -eq 32) {
                        if ($minor -lt 0) { $isOutdated = $true }
                        elseif ($minor -eq 0) {
                            if ($build1 -lt 100) { $isOutdated = $true }
                            elseif ($build1 -eq 100) {
                                if ($build2 -lt 3104) { $isOutdated = $true }
                            }
                        }
                    }
                    
                    if ($isOutdated) {
                        Write-Host "          WARNING: NPU driver version is older than recommended baseline (32.0.100.3104)." -ForegroundColor Yellow
                        Write-Host "                   This may cause OpenVINO GenAI graph compilation failures or segfaults." -ForegroundColor Yellow
                        Write-Host "                   Please update your drivers from the Intel Download Center." -ForegroundColor Yellow
                    }
                }
            }
        } catch {
            Write-Host "          Could not retrieve NPU driver version." -ForegroundColor DarkGray
        }
    }
} else {
    Write-Host "NPU:      not detected via PnP (CPU/GPU will still work)." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Preflight is informational; CPU inference works without GPU/NPU drivers." -ForegroundColor DarkGray
exit 0
