param(
    [string]$BaseUrl = "http://localhost:8000/v1",
    [string]$Model = "",
    [string]$ApiKey = "sk-dummy",
    [string]$Prompt = "What is 2+2?"
)

$ErrorActionPreference = "Stop"

function Join-Url {
    param([string]$Base, [string]$Path)
    return ($Base.TrimEnd('/') + '/' + $Path.TrimStart('/'))
}

function New-Headers {
    param([switch]$Json)
    $headers = @{}
    if ($Json) { $headers["Content-Type"] = "application/json" }
    if ($ApiKey) { $headers["Authorization"] = "Bearer $ApiKey" }
    return $headers
}

Write-Host "Open WebUI compatibility check" -ForegroundColor Cyan
Write-Host "Base URL: $BaseUrl"

$modelsUrl = Join-Url $BaseUrl "models"
Write-Host "\nChecking model list: $modelsUrl"

try {
    $modelsResponse = Invoke-RestMethod -Method Get -Uri $modelsUrl -Headers (New-Headers)
} catch {
    Write-Error "Failed to call /v1/models. Confirm the server is running and the BaseUrl is correct. $($_.Exception.Message)"
}

if ($modelsResponse.object -ne "list" -or -not $modelsResponse.data) {
    Write-Error "/v1/models did not return an OpenAI-style non-empty model list. Start the server with --model or load a model first."
}

$availableModels = @($modelsResponse.data | ForEach-Object { $_.id })
Write-Host "Models returned by /v1/models:" -ForegroundColor Green
$availableModels | ForEach-Object { Write-Host "  - $_" }

if (-not $Model) {
    $Model = $availableModels[0]
    Write-Host "\nNo -Model supplied. Using first returned model: $Model" -ForegroundColor Yellow
} elseif ($availableModels -notcontains $Model) {
    Write-Error "Requested model '$Model' was not returned by /v1/models. Returned models: $($availableModels -join ', ')"
}

$chatUrl = Join-Url $BaseUrl "chat/completions"
$nonStreamingBody = @{
    model = $Model
    messages = @(@{ role = "user"; content = $Prompt })
    stream = $false
    max_tokens = 64
} | ConvertTo-Json -Depth 10

Write-Host "\nChecking non-streaming chat completion: $chatUrl"
try {
    $chatResponse = Invoke-RestMethod -Method Post -Uri $chatUrl -Headers (New-Headers -Json) -Body $nonStreamingBody
} catch {
    Write-Error "Non-streaming /v1/chat/completions failed. $($_.Exception.Message)"
}

if (-not $chatResponse.choices -or -not $chatResponse.choices[0].message) {
    Write-Error "Chat response did not include choices[0].message."
}

$answer = $chatResponse.choices[0].message.content
Write-Host "Non-streaming response OK:" -ForegroundColor Green
Write-Host ($answer | Out-String).Trim()

$streamingBody = @{
    model = $Model
    messages = @(@{ role = "user"; content = "Write one short sentence confirming streaming works." })
    stream = $true
    max_tokens = 64
} | ConvertTo-Json -Depth 10 -Compress

Write-Host "\nChecking streaming chat completion..."
$curl = Get-Command curl.exe -ErrorAction SilentlyContinue
if (-not $curl) {
    Write-Warning "curl.exe was not found, so streaming SSE validation was skipped. Non-streaming Open WebUI compatibility passed."
    exit 0
}

$curlArgs = @(
    "-s", "-N",
    "-X", "POST", $chatUrl,
    "-H", "Content-Type: application/json"
)
if ($ApiKey) {
    $curlArgs += @("-H", "Authorization: Bearer $ApiKey")
}
$curlArgs += @("-d", $streamingBody)

$streamOutput = & curl.exe @curlArgs
$streamText = $streamOutput -join "`n"

if ($LASTEXITCODE -ne 0) {
    Write-Error "curl.exe streaming request failed with exit code $LASTEXITCODE."
}
if ($streamText -notmatch "data:") {
    Write-Error "Streaming response did not contain OpenAI-style SSE data lines."
}
if ($streamText -notmatch "data: \[DONE\]") {
    Write-Error "Streaming response did not end with data: [DONE]."
}

Write-Host "Streaming response OK." -ForegroundColor Green
Write-Host "\nOpen WebUI compatibility check passed." -ForegroundColor Green
Write-Host "Use this in Open WebUI:"
Write-Host "  Base URL: $BaseUrl"
Write-Host "  API Key:  $ApiKey"
Write-Host "  Model:    $Model"
