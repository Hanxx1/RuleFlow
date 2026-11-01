# Dot-source only; no machine/user environment configuration is changed.
$ProjectRoot = Split-Path -Parent $PSScriptRoot
function Resolve-ProjectPython([string]$Requested) {
  if ($Requested) { return $Requested }
  $local = Join-Path $ProjectRoot 'server/.venv/Scripts/python.exe'
  if (Test-Path -LiteralPath $local) { return $local }
  return (Get-Command python -ErrorAction Stop).Source
}
function Resolve-Adb {
  foreach ($sdk in @($env:ANDROID_HOME, $env:ANDROID_SDK_ROOT)) {
    if ($sdk) {
      $candidate = Join-Path $sdk 'platform-tools/adb.exe'
      if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
  }
  return (Get-Command adb -ErrorAction Stop).Source
}
function Assert-NativeSuccess([string]$Operation) {
  if ($LASTEXITCODE -ne 0) { throw "$Operation failed (exit $LASTEXITCODE)." }
}
