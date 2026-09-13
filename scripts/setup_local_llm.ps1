# 从本机 Claude Code 配置生成本地 Agent 凭据，不写入 Git。

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$sourcePath = Join-Path $HOME ".claude\settings.json"

if (-not (Test-Path -LiteralPath $sourcePath)) {
    throw "Claude Code 本地配置不存在: $sourcePath"
}

$source = Get-Content -LiteralPath $sourcePath -Raw -Encoding UTF8 | ConvertFrom-Json
$token = $source.env.ANTHROPIC_AUTH_TOKEN
$baseUrl = $source.env.ANTHROPIC_BASE_URL
$modelName = $source.env.ANTHROPIC_MODEL

if (-not $token -or -not $baseUrl -or -not $modelName) {
    throw "Claude Code 配置缺少 ANTHROPIC_AUTH_TOKEN、ANTHROPIC_BASE_URL 或 ANTHROPIC_MODEL"
}

$envText = @"
LLM_PROVIDER=anthropic
ANTHROPIC_AUTH_TOKEN=$token
ANTHROPIC_BASE_URL=$baseUrl
ANTHROPIC_MODEL=$modelName
API_TIMEOUT_MS=120000
TRAFFIC_BACKEND=sim
TRAFFIC_EMBEDDING_BACKEND=hashing
MEMORY_ENABLED=false
"@

$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText((Join-Path $projectRoot ".env"), $envText, $utf8)

$localDir = Join-Path $projectRoot ".claude"
[System.IO.Directory]::CreateDirectory($localDir) | Out-Null
$localConfig = [ordered]@{
    env = $source.env
    model = $source.model
    permissions = $source.permissions
}
[System.IO.File]::WriteAllText(
    (Join-Path $localDir "settings.local.json"),
    ($localConfig | ConvertTo-Json -Depth 12),
    $utf8
)

Write-Output "本地模型配置已生成，Token 未输出。"
