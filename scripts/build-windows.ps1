$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$MobileRoot = Join-Path $ProjectRoot 'mobile'
$DesktopProject = Join-Path $ProjectRoot 'desktop\Zhishi.RuleFlow.Desktop.csproj'
$PublishRoot = Join-Path $ProjectRoot 'desktop\bin\publish'
$ArtifactPath = Join-Path $ProjectRoot 'deliverables\Zhishi-RuleFlow-win-x64.exe'
$env:DOTNET_CLI_HOME = Join-Path $ProjectRoot '.dotnet-cli'
$env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = '1'
$env:DOTNET_NOLOGO = '1'

Push-Location $MobileRoot
try {
  npm exec vue-tsc -- --noEmit
  npm exec vite -- build --outDir web-dist --emptyOutDir
} finally {
  Pop-Location
}

dotnet publish $DesktopProject -c Release -r win-x64 --self-contained true -o $PublishRoot
Copy-Item (Join-Path $PublishRoot 'Zhishi-RuleFlow.exe') $ArtifactPath -Force
Write-Output "Windows artifact: $ArtifactPath"
