Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='py.exe'" |
  Select-Object ProcessId, @{n='CL';e={$_.CommandLine}} |
  Format-Table -AutoSize -Wrap
