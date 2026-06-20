$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "windows\convert_model.ps1") @args
if ($LASTEXITCODE -ne $null) {
    exit $LASTEXITCODE
}
