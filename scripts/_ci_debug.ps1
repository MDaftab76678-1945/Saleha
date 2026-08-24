$ErrorActionPreference = "Stop"
$git = "C:\Program Files\Git\cmd\git.exe"
$credInput = "protocol=https`nhost=github.com`n`n"
$cred = $credInput | & $git credential fill 2>$null
$tokenLine = $cred | Where-Object { $_ -like "password=*" }
if (-not $tokenLine) { Write-Output "ERROR: token nahi mila"; exit 1 }
$token = $tokenLine.Substring(9).Trim()

$headers = @{
    Authorization = "Bearer $token"
    Accept        = "application/vnd.github+json"
    "User-Agent"  = "saleha-ci-debug"
}

# ubuntu/py3.11 job id dhundo
$jobs = Invoke-RestMethod -Uri "https://api.github.com/repos/MDaftab76678-1945/aftab-alam-saleha-0.1/actions/runs/32778633949/jobs"
$target = ($jobs.jobs | Where-Object { $_.name -like "*ubuntu*3.11*" })[0]
Write-Output ("Job: " + $target.name + " id=" + $target.id)

$logs = Invoke-RestMethod -Uri "https://api.github.com/repos/MDaftab76678-1945/aftab-alam-saleha-0.1/actions/jobs/$($target.id)/logs" -Headers $headers -MaximumRedirection 5

# pip error lines nikaalo
$lines = $logs -split "`n"
$errStart = $lines | Select-String -Pattern "error|ERROR|Traceback|No matching|Could not" | Select-Object -First 15
foreach ($l in $errStart) { Write-Output ("LINE: " + $l.Line.Trim()) }
