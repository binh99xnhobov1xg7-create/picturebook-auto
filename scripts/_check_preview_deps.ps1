$ErrorActionPreference = "SilentlyContinue"
$paths = @(
  "C:\Program Files\LibreOffice\program\soffice.exe",
  "C:\Program Files (x86)\LibreOffice\program\soffice.exe"
)
$found = $false
foreach ($x in $paths) { if (Test-Path -LiteralPath $x) { Write-Host "FOUND $x"; $found = $true } }
$c = Get-Command soffice.exe -ErrorAction SilentlyContinue
if ($c) { Write-Host ("PATH " + $c.Source); $found = $true }
if (-not $found) { Write-Host "NO LibreOffice" }
& ".\.venv\Scripts\python.exe" -c "import importlib.util as u; print('python-pptx:', bool(u.find_spec('pptx'))); print('python-docx:', bool(u.find_spec('docx')))"
