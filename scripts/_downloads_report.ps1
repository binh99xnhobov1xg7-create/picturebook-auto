$ErrorActionPreference = "SilentlyContinue"
$sf = Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
$dl = $sf."{374DE290-123F-4565-9164-39C4925E467B}"
if (-not $dl -or -not (Test-Path -LiteralPath $dl)) {
    $dl = (Get-ChildItem -LiteralPath "C:\Users\Jered" -Directory -Force |
        Sort-Object { (Get-ChildItem -LiteralPath $_.FullName -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum } -Descending |
        Select-Object -First 1).FullName
}
$report = "D:\downloads_report.txt"
$lines = New-Object System.Collections.Generic.List[string]
function MB($b){ return [math]::Round($b/1MB,0) }
function FolderSize($p){ return (Get-ChildItem -LiteralPath $p -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum }

$lines.Add("PATH = " + $dl)
$lines.Add("==== Downloads top-level items (Top40, MB) ====")
Get-ChildItem -LiteralPath $dl -Force -ErrorAction SilentlyContinue | ForEach-Object {
    $sz = if ($_.PSIsContainer) { FolderSize $_.FullName } else { $_.Length }
    [PSCustomObject]@{ Name=$_.Name; MB=(MB $sz); Type= if($_.PSIsContainer){"[DIR]"}else{"[FILE]"} }
} | Sort-Object MB -Descending | Select-Object -First 40 | ForEach-Object {
    $lines.Add(("{0,8} MB   {1} {2}" -f $_.MB, $_.Type, $_.Name))
}

$lines.Add("")
$lines.Add("==== Downloads: largest 40 FILES (recursive, MB) ====")
Get-ChildItem -LiteralPath $dl -Recurse -File -Force -ErrorAction SilentlyContinue |
    Sort-Object Length -Descending | Select-Object -First 40 |
    ForEach-Object { $lines.Add(("{0,8} MB   {1}" -f (MB $_.Length), $_.FullName.Replace($dl,'...'))) }

Set-Content -LiteralPath $report -Value $lines -Encoding UTF8
Write-Host "DONE"
