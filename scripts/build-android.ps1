$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$MobileRoot = Join-Path $ProjectRoot 'mobile'
$BuildRoot = 'E:\DevTools\ZhiShiBuild'
$env:ANDROID_HOME = 'E:\DevTools\Android\Sdk'
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
$env:ANDROID_USER_HOME = 'E:\Caches\AndroidUser'
$env:GRADLE_USER_HOME = 'E:\Caches\Gradle'
$AssetRoot = Join-Path $BuildRoot 'android-assets'
$WebOutput = Join-Path $AssetRoot 'public'
$env:ZHISHI_WEB_ASSETS = $AssetRoot
Push-Location $MobileRoot
try {
  npm exec vue-tsc -- --noEmit
  New-Item -ItemType Directory -Force -Path $AssetRoot,$WebOutput | Out-Null
  npm exec vite -- build --outDir $WebOutput --emptyOutDir false
  $CapacitorConfig = Get-Content (Join-Path $MobileRoot 'android\app\src\main\assets\capacitor.config.json') -Raw | ConvertFrom-Json
  $CapacitorConfig.server.androidScheme = if ($env:VITE_API_BASE -like 'http://*') { 'http' } else { 'https' }
  $CapacitorConfig | ConvertTo-Json -Depth 10 | Set-Content (Join-Path $AssetRoot 'capacitor.config.json') -Encoding UTF8
  Copy-Item (Join-Path $MobileRoot 'android\app\src\main\assets\capacitor.plugins.json') $AssetRoot -Force
  Push-Location (Join-Path $MobileRoot 'android')
  & 'E:\DevTools\Android\gradle-8.2.1\bin\gradle.bat' --init-script (Join-Path $PSScriptRoot 'redirect-build.gradle') --project-cache-dir 'E:\Caches\Gradle\project-ZhiShi' assembleDebug --no-daemon
  Pop-Location
  Copy-Item (Join-Path $BuildRoot 'gradle\_app\outputs\apk\debug\app-debug.apk') (Join-Path $ProjectRoot 'deliverables\Zhishi-RuleFlow-debug.apk') -Force
} finally { Pop-Location }
