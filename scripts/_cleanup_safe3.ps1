# SAFE cleanup pass 3: regenerable app caches only (Cursor cache, npm cache).
# Does NOT touch chat history / logins / cloud data.
$ErrorActionPreference = "SilentlyContinue"
function GB($b){ return [math]::Round($b/1GB,2) }
$before = (Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'").FreeSpace
$R = "C:\Users\Jered\AppData\Roaming"
$L = "C:\Users\Jered\AppData\Local"

# Cursor regenerable caches (safe; rebuilt on next launch)
$cursorCache = @("Cache","Code Cache","GPUCache","CachedData","CachedExtensionVSIXs","Crashpad","logs","DawnGraphiteCache","DawnWebGPUCache","ShaderCache","GPUCache")
foreach ($n in $cursorCache) {
    $t = Join-Path "$R\Cursor" $n
    if (Test-Path -LiteralPath $t) { Remove-Item -LiteralPath $t -Recurse -Force -ErrorAction SilentlyContinue }
}
Write-Host "Cursor caches cleared"

# npm cache (regenerable)
foreach ($t in @("$L\npm-cache","$R\npm-cache")) {
    if (Test-Path -LiteralPath $t) { Remove-Item -LiteralPath $t -Recurse -Force -ErrorAction SilentlyContinue }
}
Write-Host "npm cache cleared"

$after = (Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'").FreeSpace
Write-Host ("FREED = {0} GB ; C: free now = {1} GB" -f (GB ($after-$before)), (GB $after))
