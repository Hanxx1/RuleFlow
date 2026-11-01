param([switch]$WithTests)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'environment.ps1')
$MobileRoot = Join-Path $ProjectRoot 'mobile'
if (!$env:ANDROID_HOME -and !$env:ANDROID_SDK_ROOT -and !(Test-Path -LiteralPath (Join-Path $MobileRoot 'android/local.properties'))) {
  throw 'Android SDK is not configured. Set ANDROID_HOME/ANDROID_SDK_ROOT or mobile/android/local.properties; no SDK is installed automatically.'
}

$previousAssets = $env:ZHISHI_WEB_ASSETS
try {
  $env:ZHISHI_WEB_ASSETS = $null
  Push-Location $MobileRoot
  try {
    npm.cmd run android:sync
    Assert-NativeSuccess 'Web build and Capacitor sync'
    Push-Location (Join-Path $MobileRoot 'android')
    try {
      $tasks = @('assembleDebug')
      if ($WithTests) { $tasks += 'assembleDebugAndroidTest' }
      & .\gradlew.bat @tasks --no-daemon
      Assert-NativeSuccess 'Android build'
    } finally { Pop-Location }
  } finally { Pop-Location }
  $output = Join-Path $ProjectRoot 'deliverables'
  New-Item -ItemType Directory -Force -Path $output | Out-Null
  Copy-Item -LiteralPath (Join-Path $MobileRoot 'android/app/build/outputs/apk/debug/app-debug.apk') -Destination (Join-Path $output 'Zhishi-RuleFlow-debug.apk') -Force
  if ($WithTests) {
    Copy-Item -LiteralPath (Join-Path $MobileRoot 'android/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk') -Destination (Join-Path $output 'Zhishi-RuleFlow-androidTest.apk') -Force
  }
} finally { $env:ZHISHI_WEB_ASSETS = $previousAssets }
