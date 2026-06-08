$ErrorActionPreference = "SilentlyContinue"
function GB($b){ return [math]::Round($b/1GB,2) }
$p = "C:\Users\Jered\Downloads"
if (Test-Path -LiteralPath $p) {
  $s = (Get-ChildItem -LiteralPath $p -Recurse -Force | Measure-Object Length -Sum).Sum
  Write-Host ("Downloads total = {0} GB" -f (GB $s))
  Write-Host "--- top items ---"
  Get-ChildItem -LiteralPath $p -Force | ForEach-Object {
    $z = if ($_.PSIsContainer) { (Get-ChildItem -LiteralPath $_.FullName -Recurse -Force | Measure-Object Length -Sum).Sum } else { $_.Length }
    [pscustomobject]@{ G=(GB $z); N=$_.Name }
  } | Sort-Object G -Descending | Select-Object -First 12 | ForEach-Object {
    Write-Host ("{0,8} GB  {1}" -f $_.G, $_.N)
  }
} else { Write-Host "Downloads NOT FOUND" }
