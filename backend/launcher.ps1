# AI Music Analysis Launcher

# Starts server first, then opens browser

Write-Host "====================================" -ForegroundColor Cyan

Write-Host "  AI Music Analysis Server" -ForegroundColor Cyan

Write-Host "====================================" -ForegroundColor Cyan

Write-Host ""

${python} = "C:\Users\18534\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

 ${server} = "C:\Users\18534\Documents\AI“Ù¿÷≤˙∆∑\backend\server.py"
Write-Host "Starting server..." -ForegroundColor Yellow

Write-Host ""

Start-Process -WindowStyle Hidden -FilePath ${python} -ArgumentList ${server}

Write-Host "Waiting for server to start..." -NoNewline

Start-Sleep -Seconds 3

Write-Host " done"

Write-Host ""

Write-Host "Opening browser: http://127.0.0.1:5002" -ForegroundColor Green

Start-Process "http://127.0.0.1:5002"

Write-Host ""

Write-Host "To stop the server, press Ctrl+C in this window." -ForegroundColor Gray

