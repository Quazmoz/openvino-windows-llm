$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "windows\check_hardware.ps1") @args
if ($LASTEXITCODE -ne $null) {
    exit $LASTEXITCODE
}
