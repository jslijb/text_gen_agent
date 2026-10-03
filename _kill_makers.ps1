param([string]$Pattern)
$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'"
$killed = @()
foreach ($pr in $procs) {
  if ($pr.CommandLine -match $Pattern) {
    Stop-Process -Id $pr.ProcessId -Force -ErrorAction SilentlyContinue
    $killed += $pr.ProcessId
  }
}
"killed: " + ($killed -join ',')
