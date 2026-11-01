$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
. (Join-Path $PSScriptRoot 'environment.ps1')
$MobileRoot = Join-Path $ProjectRoot 'mobile'
$DesktopProject = Join-Path $ProjectRoot 'desktop\Zhishi.RuleFlow.Desktop.csproj'
$PublishRoot = Join-Path $ProjectRoot 'desktop\bin\publish'
$ArtifactPath = Join-Path $ProjectRoot 'deliverables\Zhishi-RuleFlow-win-x64.exe'
$env:DOTNET_CLI_HOME = Join-Path $ProjectRoot '.dotnet-cli'
$env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = '1'
$env:DOTNET_NOLOGO = '1'

Push-Location $MobileRoot
try {
  npm.cmd run build
  Assert-NativeSuccess 'Web build'
} finally {
  Pop-Location
}

dotnet publish $DesktopProject -c Release -r win-x64 --self-contained true -o $PublishRoot
Assert-NativeSuccess 'Desktop publish'
New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot 'deliverables') | Out-Null
Copy-Item (Join-Path $PublishRoot 'Zhishi-RuleFlow.exe') $ArtifactPath -Force
Write-Output "Windows artifact: $ArtifactPath"
