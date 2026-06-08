$ErrorActionPreference = "SilentlyContinue"
$roots = @("C:\Users\Jered\picturebook-auto\outputs", "D:\picturebook_outputs")
foreach ($r in $roots) {
  Write-Host ("##### ROOT: {0} #####" -f $r)
  if (-not (Test-Path -LiteralPath $r)) { Write-Host "  (missing)"; continue }
  Get-ChildItem -LiteralPath $r -Directory -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | ForEach-Object {
    $imgs = Get-ChildItem -LiteralPath $_.FullName -Recurse -File -ErrorAction SilentlyContinue |
      Where-Object { $_.Extension -eq ".png" -and $_.FullName -notmatch "_refsheets" -and $_.Name -match "page_" }
    Write-Host ("{0}  | page imgs={1} | {2}" -f $_.LastWriteTime.ToString("MM-dd HH:mm"), $imgs.Count, $_.Name)
  }
}
