# Disk usage report (read-only). Writes UTF-8 file to avoid console mojibake.
$ErrorActionPreference = "SilentlyContinue"
$base = "C:\Users\Jered"
$report = "D:\disk_report.txt"
$lines = New-Object System.Collections.Generic.List[string]

function MB($bytes) { return [math]::Round($bytes / 1MB, 0) }
function GB($bytes) { return [math]::Round($bytes / 1GB, 1) }
function FolderSize($p) {
    return (Get-ChildItem -LiteralPath $p -Recurse -File -Force -ErrorAction SilentlyContinue |
            Measure-Object -Property Length -Sum).Sum
}

$lines.Add("==== FREE SPACE ====")
Get-CimInstance Win32_LogicalDisk | ForEach-Object {
    $lines.Add(("{0}  free {1} GB / total {2} GB" -f $_.DeviceID, (GB $_.FreeSpace), (GB $_.Size)))
}

$lines.Add("")
$lines.Add("==== FOLDERS under C:\Users\Jered (MB, sorted) ====")
Get-ChildItem -LiteralPath $base -Directory -Force -ErrorAction SilentlyContinue | ForEach-Object {
    [PSCustomObject]@{ Folder = $_.Name; MB = (MB (FolderSize $_.FullName)) }
} | Sort-Object MB -Descending | ForEach-Object {
    $lines.Add(("{0,8} MB   {1}" -f $_.MB, $_.Folder))
}

$lines.Add("")
$lines.Add("==== DESKTOP items (Top30, MB) ====")
Get-ChildItem -LiteralPath "$base\Desktop" -Force -ErrorAction SilentlyContinue | ForEach-Object {
    $sz = if ($_.PSIsContainer) { FolderSize $_.FullName } else { $_.Length }
    [PSCustomObject]@{ Name = $_.Name; MB = (MB $sz); Type = if ($_.PSIsContainer) {"[DIR]"} else {"[FILE]"} }
} | Sort-Object MB -Descending | Select-Object -First 30 | ForEach-Object {
    $lines.Add(("{0,8} MB   {1} {2}" -f $_.MB, $_.Type, $_.Name))
}

$lines.Add("")
$lines.Add("==== AppData\Local subfolders (Top20, MB) ====")
Get-ChildItem -LiteralPath "$base\AppData\Local" -Directory -Force -ErrorAction SilentlyContinue | ForEach-Object {
    [PSCustomObject]@{ Name = $_.Name; MB = (MB (FolderSize $_.FullName)) }
} | Sort-Object MB -Descending | Select-Object -First 20 | ForEach-Object {
    $lines.Add(("{0,8} MB   {1}" -f $_.MB, $_.Name))
}

$lines.Add("")
$lines.Add("==== CACHE / TEMP / RECYCLE ====")
$checks = @(
    @("UserTemp",    "$base\AppData\Local\Temp"),
    @("WindowsTemp", "C:\Windows\Temp"),
    @("EdgeCache",   "$base\AppData\Local\Microsoft\Edge"),
    @("ChromeCache", "$base\AppData\Local\Google\Chrome"),
    @("PipCache",    "$base\AppData\Local\pip\Cache"),
    @("NpmCache",    "$base\AppData\Local\npm-cache"),
    @("RecycleBin",  'C:\$Recycle.Bin')
)
foreach ($c in $checks) {
    if (Test-Path -LiteralPath $c[1]) {
        $lines.Add(("{0,8} MB   {1}  ({2})" -f (MB (FolderSize $c[1])), $c[0], $c[1]))
    }
}

$lines.Add("")
$lines.Add("==== TOP 40 LARGEST FILES under C:\Users\Jered (MB) ====")
Get-ChildItem -LiteralPath $base -Recurse -File -Force -ErrorAction SilentlyContinue |
    Sort-Object Length -Descending | Select-Object -First 40 |
    ForEach-Object { $lines.Add(("{0,8} MB   {1}" -f (MB $_.Length), $_.FullName)) }

Set-Content -LiteralPath $report -Value $lines -Encoding UTF8
Write-Host "REPORT WRITTEN"
