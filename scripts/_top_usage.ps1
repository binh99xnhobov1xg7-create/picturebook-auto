$ErrorActionPreference = "SilentlyContinue"
function GB($b){ return [math]::Round($b/1GB,2) }
function Size($p){ (Get-ChildItem -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum }

$c = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
$d = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='D:'"
Write-Host ("C: free = {0} GB / total {1} GB" -f (GB $c.FreeSpace), (GB $c.Size))
Write-Host ("D: free = {0} GB / total {1} GB" -f (GB $d.FreeSpace), (GB $d.Size))
Write-Host "--- top folders under C:\Users\Jered ---"

$targets = @(
  "C:\Users\Jered\下载",
  "C:\Users\Jered\Desktop",
  "C:\Users\Jered\AppData",
  "C:\Users\Jered\Documents",
  "C:\Users\Jered\picturebook-auto"
)
foreach ($t in $targets) {
  if (Test-Path -LiteralPath $t) { Write-Host ("{0,8} GB  {1}" -f (GB (Size $t)), $t) }
}
