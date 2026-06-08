$ErrorActionPreference = "SilentlyContinue"
function GB($b){ return [math]::Round($b/1GB,2) }
$b = (Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'").FreeSpace
$t = "C:\Users\Jered\AppData\Roaming\baidu\BaiduNetdisk\AutoUpdate\Download"
if (Test-Path -LiteralPath $t) { Remove-Item -LiteralPath $t -Recurse -Force -ErrorAction SilentlyContinue }
$a = (Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'").FreeSpace
Write-Host ("FREED = {0} GB ; C: free now = {1} GB" -f (GB ($a-$b)), (GB $a))
