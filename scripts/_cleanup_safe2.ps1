# SAFE cleanup pass 2: browser caches, crash dumps, WER, thumbnails, orphan office locks.
# Does NOT delete cookies/passwords/history/personal files.
$ErrorActionPreference = "SilentlyContinue"
$L = "C:\Users\Jered\AppData\Local"
function GB($b){ return [math]::Round($b/1GB,2) }
$before = (Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'").FreeSpace

# 1) Browser caches (only Cache-type subfolders; keeps logins/history)
$cacheNames = @("Cache","Code Cache","GPUCache","DawnGraphiteCache","DawnWebGPUCache","ShaderCache","GrShaderCache")
$roots = @("$L\Microsoft\Edge\User Data", "$L\Google\Chrome\User Data", "$L\Microsoft\Edge\User Data\Default\Service Worker")
foreach ($r in $roots) {
    if (Test-Path -LiteralPath $r) {
        Get-ChildItem -LiteralPath $r -Recurse -Directory -Force -ErrorAction SilentlyContinue |
            Where-Object { $cacheNames -contains $_.Name } |
            ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
    }
}
Write-Host "1) browser caches cleared"

# 2) Crash dumps + WER (error reports)
foreach ($p in @("$L\CrashDumps",
                 "$L\Microsoft\Windows\WER",
                 "C:\ProgramData\Microsoft\Windows\WER",
                 "$L\D3DSCache")) {
    if (Test-Path -LiteralPath $p) {
        Get-ChildItem -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }
}
Write-Host "2) crash dumps + WER cleared"

# 3) Thumbnail/icon cache (regenerates automatically)
Get-ChildItem -LiteralPath "$L\Microsoft\Windows\Explorer" -Filter "thumbcache_*.db" -Force -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem -LiteralPath "$L\Microsoft\Windows\Explorer" -Filter "iconcache_*.db" -Force -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Write-Host "3) thumbnail cache cleared"

# 4) Orphan Office lock files (~$xxxx) on Desktop/Documents/Downloads
foreach ($p in @("C:\Users\Jered\Desktop","C:\Users\Jered\Documents","C:\Users\Jered\下载")) {
    if (Test-Path -LiteralPath $p) {
        Get-ChildItem -LiteralPath $p -Recurse -Force -Filter "~`$*" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    }
}
Write-Host "4) orphan office lock files cleared"

# 5) My own temp report files on D:
foreach ($p in @("D:\disk_report.txt","D:\downloads_report.txt")) {
    Remove-Item -LiteralPath $p -Force -ErrorAction SilentlyContinue
}
Write-Host "5) temp reports removed"

# 6) Re-empty recycle bin
Clear-RecycleBin -Force -ErrorAction SilentlyContinue

$after = (Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'").FreeSpace
Write-Host ("C: free BEFORE = {0} GB" -f (GB $before))
Write-Host ("C: free AFTER  = {0} GB" -f (GB $after))
Write-Host ("FREED = {0} GB" -f (GB ($after - $before)))
