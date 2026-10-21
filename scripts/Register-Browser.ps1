param(
    [Parameter(Mandatory=$true)][ValidateSet('Edge','Chrome','Firefox')][string]$Browser,
    [string]$ExtensionId
)
$ErrorActionPreference = 'Stop'
$AppRoot = Split-Path -Parent $PSScriptRoot
$HostExe = Join-Path $AppRoot 'SubtitleDeskHost.exe'
if (!(Test-Path -LiteralPath $HostExe -PathType Leaf)) { throw 'Run this script from the packaged application folder.' }
$HostName = 'vn.subtitledesk.bridge'
$RegistryBase = switch ($Browser) {
    Edge { 'Software\Microsoft\Edge\NativeMessagingHosts' }
    Chrome { 'Software\Google\Chrome\NativeMessagingHosts' }
    Firefox { 'Software\Mozilla\NativeMessagingHosts' }
}
$Manifest = @{
    name = $HostName
    description = 'SubtitleDesk browser bridge'
    path = $HostExe
    type = 'stdio'
}
if ($Browser -eq 'Firefox') {
    $Manifest.allowed_extensions = @('subtitledesk@local.invalid')
} else {
    if ($ExtensionId -notmatch '^[a-p]{32}$') { throw 'Supply the 32-character ID shown on the browser extensions page.' }
    $Manifest.allowed_origins = @("chrome-extension://$ExtensionId/")
}
$ManifestDir = Join-Path $AppRoot 'data\browser'
[IO.Directory]::CreateDirectory($ManifestDir) | Out-Null
$ManifestPath = Join-Path $ManifestDir "$Browser.json"
$RegistryPath = "$RegistryBase\$HostName"
$Existing = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($RegistryPath)
if ($Existing) {
    $OldPath = [string]$Existing.GetValue('')
    $Existing.Dispose()
    if ($OldPath -and $OldPath -ne $ManifestPath) {
        throw "Another installation is registered at $OldPath. Unregister it before changing installations."
    }
}
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($ManifestPath, ($Manifest | ConvertTo-Json -Depth 5), $Utf8NoBom)
$Key = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($RegistryPath)
try { $Key.SetValue('', $ManifestPath, [Microsoft.Win32.RegistryValueKind]::String) }
finally { $Key.Dispose() }
Write-Output "Registered SubtitleDesk for $Browser for the current Windows user."
