param(
  [ValidateSet('Prepare','Server','ServerOnline','Install','Check','ShareText','TestShares')][string]$Action='Check',
  [string]$Serial,
  [string]$PythonPath
)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'environment.ps1')
$PythonPath=Resolve-ProjectPython $PythonPath
$Adb=$null
$Apk=Join-Path $ProjectRoot 'deliverables\Zhishi-RuleFlow-usb-debug.apk'

function Invoke-Adb {
  & $Adb @script:DeviceArgs @args
  if($LASTEXITCODE -ne 0){throw 'ADB操作失败，请检查设备授权和连接。'}
}
function Select-Device {
  $script:Adb=Resolve-Adb
  if(!(Test-Path -LiteralPath $Adb)){throw '未找到ADB，请配置已安装SDK路径。'}
  $devices=@(& $Adb devices | Select-String '^([^\s]+)\s+device$' | ForEach-Object {$_.Matches[0].Groups[1].Value})
  if($Serial){if($Serial -notin $devices){throw '指定设备未连接或未授权。'}}
  elseif($devices.Count -eq 1){$script:Serial=$devices[0]}
  else{throw '需要一个已授权USB设备；多设备时传入-Serial。请在手机启用USB调试并确认电脑授权。'}
  $script:DeviceArgs=@('-s',$script:Serial)
}

switch($Action){
  'Prepare' {
    $previousBase=$env:VITE_API_BASE
    try {
      $env:VITE_API_BASE='http://127.0.0.1:8000'
      & (Join-Path $PSScriptRoot 'build-android.ps1')
      if($LASTEXITCODE -ne 0){throw 'APK构建失败。'}
      Copy-Item -LiteralPath (Join-Path $ProjectRoot 'deliverables\Zhishi-RuleFlow-debug.apk') -Destination $Apk -Force
      Write-Output ('USB联调包：'+$Apk)
      Write-Output ('SHA256：'+(Get-FileHash -LiteralPath $Apk -Algorithm SHA256).Hash)
    } finally {$env:VITE_API_BASE=$previousBase}
  }
  'Server' {
    $runtime=Join-Path $ProjectRoot '.runtime\android-usb'
    New-Item -ItemType Directory -Path $runtime -Force | Out-Null
    $env:DATABASE_PATH=Join-Path $runtime 'ruleflow.db'
    $env:VAULT_UPLOAD_ROOT=Join-Path $runtime 'vault'
    $env:DOCUMENT_UPLOAD_ROOT=Join-Path $runtime 'documents'
    $env:DEMO_MODE='false'
    $env:LLM_BASE_URL=''
    $env:LLM_MODEL=''
    $env:CORS_ORIGINS='http://localhost,https://localhost,http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5193'
    $pepperBytes=New-Object byte[] 32
    $random=[Security.Cryptography.RandomNumberGenerator]::Create()
    try {$random.GetBytes($pepperBytes)}finally{$random.Dispose()}
    $env:REFRESH_TOKEN_PEPPER=[Convert]::ToBase64String($pepperBytes)
    Write-Output '启动本机USB测试后端。窗口需保持运行；Ctrl+C停止。重启后需要重新登录。'
    Push-Location (Join-Path $ProjectRoot 'server')
    try {& $PythonPath -m uvicorn app.main:app --host 127.0.0.1 --port 8000}
    finally {Pop-Location}
  }
  'ServerOnline' {
    & (Join-Path $PSScriptRoot 'start-deepseek-backend.ps1') -Port 8000 -PythonPath $PythonPath
  }
  'Install' {
    Select-Device
    if(!(Test-Path -LiteralPath $Apk)){throw 'USB APK不存在，请先运行-Action Prepare。'}
    $health=Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 5
    if($health.data.status -ne 'ok'){throw '后端未就绪，请先在另一终端运行-Action Server。'}
    Invoke-Adb reverse tcp:8000 tcp:8000
    Invoke-Adb install -r $Apk
    Invoke-Adb shell am start -n com.zhishi.ruleflow/.MainActivity
    Write-Output '已安装并启动。USB需保持连接；进入应用注册/登录并执行验收文档。'
  }
  'Check' {
    Select-Device
    Invoke-Adb reverse --list
    Invoke-Adb shell pm path com.zhishi.ruleflow
    $health=Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 5
    Write-Output ('电脑端健康状态：'+$health.data.status)
    Write-Output '以上只确认设备/包/电脑端后端；手机WebView实际连通仍需应用健康检查和登录验证。'
  }
  'ShareText' {
    Select-Device
    Invoke-Adb shell am start -n com.zhishi.ruleflow/.ShareReceiverActivity -a android.intent.action.SEND -t text/plain --es android.intent.extra.TEXT 'Android-share-test'
    Write-Output '已发送无个人信息的测试文字。检查应用进入导入页、待确认且未自动上传。'
  }
  'TestShares' {
    Select-Device
    $testApk=Join-Path $ProjectRoot 'deliverables\Zhishi-RuleFlow-androidTest.apk'
    if(!(Test-Path -LiteralPath $testApk)){throw '测试APK不存在，请先编译assembleDebugAndroidTest并复制测试产物。'}
    Invoke-Adb install -r $testApk
    Invoke-Adb shell am instrument -w -e class com.zhishi.ruleflow.ShareReceiverInstrumentedTest com.zhishi.ruleflow.test/androidx.test.runner.AndroidJUnitRunner
    Write-Output '请核对输出中的OK及测试数量；ADB命令成功不等于断言通过。运行期间不要同时发送真实分享内容。'
  }
}
