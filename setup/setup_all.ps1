$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "windows\setup_all.ps1") @args
if ($LASTEXITCODE -ne $null) {
    exit $LASTEXITCODE
}
