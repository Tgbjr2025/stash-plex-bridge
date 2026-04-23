$ErrorActionPreference = 'Stop'

$packageName = 'stash-plex-bridge'
$url         = 'https://github.com/Tgbjr2025/stash-plex-bridge/releases/download/v1.0.0/stash-plex-bridge-source.zip'
$checksum    = 'REPLACE_WITH_ACTUAL_SHA256_FROM_RELEASE'
$toolsDir    = "$(Split-Path -parent $MyInvocation.MyCommand.Definition)"

$packageArgs = @{
  packageName    = $packageName
  unzipLocation  = $toolsDir
  url            = $url
  checksum       = $checksum
  checksumType   = 'sha256'
}

Install-ChocolateyZipPackage @packageArgs

$installPs1 = Join-Path $toolsDir 'install.ps1'
Install-ChocolateyPowerShellCommand `
  -PackageName $packageName `
  -PSFileFullPath $installPs1
