param([string]$Destination = (Join-Path $env:LOCALAPPDATA 'Programs\SubtitleDesk'))
$ErrorActionPreference = 'Stop'
$SourceRoot = Split-Path -Parent $PSScriptRoot
$DestinationFull = [IO.Path]::GetFullPath($Destination)
if (Test-Path -LiteralPath $DestinationFull) { throw 'Destination already exists. Choose a NEW dedicated folder; nothing was overwritten.' }
if (!(Test-Path -LiteralPath (Join-Path $SourceRoot 'SubtitleDesk.exe'))) { throw 'Use Install.ps1 from the portable package.' }
[IO.Directory]::CreateDirectory($DestinationFull) | Out-Null
Get-ChildItem -LiteralPath $SourceRoot -Force | Where-Object { $_.Name -ne 'data' } |
    Copy-Item -Destination $DestinationFull -Recurse
Write-Output "Installed in $DestinationFull. Run SubtitleDesk.exe. Browser registration is optional and separate."
