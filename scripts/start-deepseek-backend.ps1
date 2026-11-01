param([int]$Port=8000,[string]$PythonPath)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'environment.ps1')
$PythonPath=Resolve-ProjectPython $PythonPath
$privatePath=Join-Path $ProjectRoot '.runtime\deepseek\private.json'
if(!(Test-Path -LiteralPath $privatePath)){throw '缺少本机私有DeepSeek配置；不要把密钥提交Git。'}
$settings=Get-Content -LiteralPath $privatePath -Raw | ConvertFrom-Json
foreach($field in @('LLM_BASE_URL','LLM_MODEL','LLM_API_KEY','LLM_THINKING','LLM_TIMEOUT_SECONDS','LLM_MAX_OUTPUT_TOKENS')){
  [Environment]::SetEnvironmentVariable($field,[string]$settings.$field,'Process')
}
# Isolated development data; never replace an existing production database.
$runtime=Join-Path $ProjectRoot '.runtime\deepseek\server'
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
$env:DATABASE_PATH=Join-Path $runtime 'ruleflow.db'
$env:DOCUMENT_UPLOAD_ROOT=Join-Path $runtime 'documents'
$env:VAULT_UPLOAD_ROOT=Join-Path $runtime 'vault'
$env:DEMO_MODE='false'
$env:CORS_ORIGINS='http://localhost,https://localhost,http://127.0.0.1:5193,http://127.0.0.1:5173,http://localhost:5173'
Write-Output '启动已配置DeepSeek的本机开发后端；只监听127.0.0.1，Ctrl+C停止。'
Push-Location (Join-Path $ProjectRoot 'server')
try {& $PythonPath -m uvicorn app.main:app --host 127.0.0.1 --port $Port}
finally {Pop-Location}
