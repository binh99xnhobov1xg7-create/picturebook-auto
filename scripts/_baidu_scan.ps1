$ErrorActionPreference = "SilentlyContinue"
function GB($b){ return [math]::Round($b/1GB,3) }
function Size($p){ (Get-ChildItem -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum }
$roots = @("C:\Users\Jered\AppData\Roaming\baidu","C:\Users\Jered\AppData\Local\baidu")
foreach ($r in $roots) {
  if (Test-Path -LiteralPath $r) {
    Write-Host ("=== {0}  ({1} GB) ===" -f $r, (GB (Size $r)))
    Get-ChildItem -LiteralPath $r -Recurse -Directory -Force -ErrorAction SilentlyContinue |
      ForEach-Object { [pscustomobject]@{ G=(GB (Size $_.FullName)); P=$_.FullName } } |
      Where-Object { $_.G -ge 0.05 } | Sort-Object G -Descending | Select-Object -First 25 |
      ForEach-Object { Write-Host ("{0,8} GB  {1}" -f $_.G, $_.P) }
  }
}
