$ErrorActionPreference = "SilentlyContinue"
Add-Type -AssemblyName System.Drawing
$since = (Get-Date).Date
$roots = @("C:\Users\Jered\picturebook-auto\outputs", "D:\picturebook_outputs")
$rows = @()
foreach ($r in $roots) {
  if (Test-Path -LiteralPath $r) {
    Get-ChildItem -LiteralPath $r -Recurse -File -ErrorAction SilentlyContinue |
      Where-Object { $_.Extension -eq ".png" -and $_.LastWriteTime -ge $since } |
      ForEach-Object {
        $w=0; $h=0
        try { $img=[System.Drawing.Image]::FromFile($_.FullName); $w=$img.Width; $h=$img.Height; $img.Dispose() } catch {}
        $ratio = if ($h -gt 0) { [math]::Round($w/$h,3) } else { 0 }
        $rows += [pscustomobject]@{ KB=[math]::Round($_.Length/1KB); WxH=("{0}x{1}" -f $w,$h); Ratio=$ratio; Time=$_.LastWriteTime.ToString("HH:mm"); Path=$_.FullName }
      }
  }
}
$rows = $rows | Sort-Object Path
Write-Host ("total today PNG = {0}" -f $rows.Count)
$rows | ForEach-Object { Write-Host ("{0,7}KB  {1,-11} r={2,-6} {3}  {4}" -f $_.KB, $_.WxH, $_.Ratio, $_.Time, $_.Path) }
