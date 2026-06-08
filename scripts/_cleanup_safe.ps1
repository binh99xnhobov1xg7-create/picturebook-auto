# SAFE cleanup: recycle bin, temp, package caches, our own project outputs.
# Does NOT touch personal files (Downloads/Desktop/Documents) or app logins.
$ErrorActionPreference = "SilentlyContinue"

function GB($b){ return [math]::Round($b/1GB,2) }
$before = (Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'").FreeSpace
Write-Host ("C: free BEFORE = {0} GB" -f (GB $before))

function ClearDirContents($p) {
    if (Test-Path -LiteralPath $p) {
        Get-ChildItem -LiteralPath $p -Force -ErrorAction SilentlyContinue |
            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host ("  cleared: {0}" -f $p)
    }
}

Write-Host "1) Recycle Bin..."
Clear-RecycleBin -Force -ErrorAction SilentlyContinue
try { Clear-RecycleBin -Confirm:$false -ErrorAction SilentlyContinue } catch {}

Write-Host "2) Temp folders..."
ClearDirContents "$env:TEMP"
ClearDirContents "C:\Windows\Temp"

Write-Host "3) Package caches (npm / pip)..."
ClearDirContents "C:\Users\Jered\AppData\Local\npm-cache"
ClearDirContents "C:\Users\Jered\AppData\Local\pip\Cache"

Write-Host "4) Project __pycache__ ..."
Get-ChildItem -LiteralPath "C:\Users\Jered\picturebook-auto" -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "5) Project outputs (keep only L5_Friends_v4) ..."
$outRoot = "C:\Users\Jered\picturebook-auto\outputs"
if (Test-Path -LiteralPath $outRoot) {
    Get-ChildItem -LiteralPath $outRoot -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne "L5_Friends_v4" } |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  outputs cleaned (kept L5_Friends_v4)"
}

$after = (Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'").FreeSpace
Write-Host ("C: free AFTER  = {0} GB" -f (GB $after))
Write-Host ("FREED = {0} GB" -f (GB ($after - $before)))
