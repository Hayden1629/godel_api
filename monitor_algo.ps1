# Barebones Windows monitor script for algo_loop.py
# Monitors the process and restarts it if it closes

$scriptPath = Join-Path $PSScriptRoot "algo_loop.py"
$pythonExe = "python"

Write-Host "Starting monitor for algo_loop.py..."
Write-Host "Script path: $scriptPath"
Write-Host "Press Ctrl+C to stop monitoring`n"

while ($true) {
    $process = Start-Process -FilePath $pythonExe -ArgumentList $scriptPath -PassThru -NoNewWindow -Wait
    
    if ($process.ExitCode -ne 0) {
        Write-Host "`n[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Process exited with code $($process.ExitCode)" -ForegroundColor Yellow
        Write-Host "Restarting in 5 seconds..." -ForegroundColor Yellow
        Start-Sleep -Seconds 5
    } else {
        Write-Host "`n[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Process exited normally" -ForegroundColor Green
        Write-Host "Restarting in 5 seconds..." -ForegroundColor Yellow
        Start-Sleep -Seconds 5
    }
}

