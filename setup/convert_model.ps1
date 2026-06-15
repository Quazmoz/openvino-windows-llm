<#
.SYNOPSIS
    Convert a Hugging Face model to OpenVINO IR using Optimum Intel.

.DESCRIPTION
    Thin wrapper over `python -m runtime.model_converter`. Resolves a model by its
    models.json id, or takes an explicit source model + output directory.
    Requires the conversion dependencies (run setup with -WithConvert first).

.PARAMETER Id
    Model id from models.json (resolves source model, output path, weight format).

.PARAMETER Model
    Hugging Face source model id (use with -Output).

.PARAMETER Output
    Output directory for the OpenVINO IR model (use with -Model).

.PARAMETER WeightFormat
    Quantization: int4 (default), int8, or fp16.

.EXAMPLE
    .\setup\convert_model.ps1 -Id tinyllama-1.1b-chat

.EXAMPLE
    .\setup\convert_model.ps1 -Model Qwen/Qwen2.5-1.5B-Instruct -Output models\openvino\qwen2.5-1.5b-instruct-int4
#>
[CmdletBinding(DefaultParameterSetName = "ById")]
param(
    [Parameter(ParameterSetName = "ById", Mandatory = $true)]
    [string]$Id,

    [Parameter(ParameterSetName = "ByModel", Mandatory = $true)]
    [string]$Model,

    [Parameter(ParameterSetName = "ByModel", Mandatory = $true)]
    [string]$Output,

    [string]$WeightFormat = "int4"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "ERROR: venv not found. Run .\setup.bat -WithConvert first." -ForegroundColor Red
    exit 1
}

Push-Location $RepoRoot
try {
    if ($PSCmdlet.ParameterSetName -eq "ById") {
        & $venvPython -m runtime.model_converter --id $Id --weight-format $WeightFormat
    } else {
        & $venvPython -m runtime.model_converter --model $Model --output $Output --weight-format $WeightFormat
    }
} finally {
    Pop-Location
}
