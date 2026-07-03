$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "windows\install_deps.ps1") @args
if ($LASTEXITCODE -ne $null) {
    exit $LASTEXITCODE
}
