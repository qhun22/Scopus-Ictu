# Scopus-ICTU startup script
# Run: powershell -ExecutionPolicy Bypass -File start-server.ps1

$BackendDir = "$PSScriptRoot\backend"
$CloudflaredExe = "C:\cloudflared\cloudflared.exe"
$TunnelName = "scopus-ictu"

Write-Host "=== Scopus-ICTU Server ===" -ForegroundColor Cyan

# Start backend in a new window
Write-Host "Starting backend on http://127.0.0.1:8000 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$BackendDir'; uvicorn app.main:app --host 127.0.0.1 --port 8000" -WindowStyle Normal

# Wait for backend to be ready
Write-Host "Waiting for backend to start..." -ForegroundColor Yellow
$timeout = 15
$elapsed = 0
do {
    Start-Sleep -Seconds 1
    $elapsed++
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { break }
    } catch {}
} while ($elapsed -lt $timeout)

if ($elapsed -ge $timeout) {
    Write-Host "Backend did not respond within ${timeout}s — check the window for errors." -ForegroundColor Red
} else {
    Write-Host "Backend ready." -ForegroundColor Green
}

# Start Cloudflare tunnel in a new window
Write-Host "Starting Cloudflare tunnel -> https://scopus-ictu.xyz ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& '$CloudflaredExe' tunnel run $TunnelName" -WindowStyle Normal

Write-Host ""
Write-Host "Done! Open https://scopus-ictu.xyz in your browser." -ForegroundColor Cyan
Write-Host "Close the two opened windows to stop the server and tunnel." -ForegroundColor Gray
