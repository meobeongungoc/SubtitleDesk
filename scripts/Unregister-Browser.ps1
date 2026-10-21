param([Parameter(Mandatory=$true)][ValidateSet('Edge','Chrome','Firefox')][string]$Browser)
$ErrorActionPreference = 'Stop'
$AppRoot = Split-Path -Parent $PSScriptRoot
$ManifestPath = Join-Path $AppRoot "data\browser\$Browser.json"
$RegistryBase = switch ($Browser) {
    Edge { 'Software\Microsoft\Edge\NativeMessagingHosts' }
    Chrome { 'Software\Google\Chrome\NativeMessagingHosts' }
    Firefox { 'Software\Mozilla\NativeMessagingHosts' }
}
$RegistryPath = "$RegistryBase\vn.subtitledesk.bridge"
$Key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($RegistryPath)
if ($Key) {
    $CurrentPath = [string]$Key.GetValue('')
    $Key.Dispose()
    if ($CurrentPath -ne $ManifestPath) { throw 'Registration belongs to another installation; left unchanged.' }
    [Microsoft.Win32.Registry]::CurrentUser.DeleteSubKey($RegistryPath, $false)
}
Write-Output "Unregistered SubtitleDesk for $Browser. Settings and files were retained."
