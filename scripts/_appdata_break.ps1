$ErrorActionPreference = "SilentlyContinue"
function GB($b){ return [math]::Round($b/1GB,2) }
function Size($p){ (Get-ChildItem -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum }

# Resolve real Downloads path from registry
$dl = (Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")."{374DE290-123F-4565-9164-39C4925E467B}"
Write-Host ("Downloads path = {0}" -f $dl)
if ($dl -and (Test-Path -LiteralPath $dl)) { Write-Host ("Downloads size = {0} GB" -f (GB (Size $dl))) }

Write-Host "--- top AppData\Local subfolders (>0.3GB) ---"
Get-ChildItem -LiteralPath "C:\Users\Jered\AppData\Local" -Directory -Force -ErrorAction SilentlyContinue |
  ForEach-Object { [pscustomobject]@{ G=(GB (Size $_.FullName)); P=$_.FullName } } |
  Where-Object { $_.G -ge 0.3 } | Sort-Object G -Descending |
  ForEach-Object { Write-Host ("{0,8} GB  {1}" -f $_.G, $_.P) }

Write-Host "--- top AppData\Roaming subfolders (>0.3GB) ---"
Get-ChildItem -LiteralPath "C:\Users\Jered\AppData\Roaming" -Directory -Force -ErrorAction SilentlyContinue |
  ForEach-Object { [pscustomobject]@{ G=(GB (Size $_.FullName)); P=$_.FullName } } |
  Where-Object { $_.G -ge 0.3 } | Sort-Object G -Descending |
  ForEach-Object { Write-Host ("{0,8} GB  {1}" -f $_.G, $_.P) }
