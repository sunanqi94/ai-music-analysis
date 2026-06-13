# AI Music Analysis - Run Server
Write-Host "====================================" -ForegroundColor Cyan
Write-Host "  AI Music Analysis Server" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""
${python} = "C:\Users\18534\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
${server} = "C:\Users\18534\Desktop\codex（ai音乐分析助手）\backend\server.py"
Write-Host "Starting server..." -ForegroundColor Yellow
Start-Process -WindowStyle Hidden -FilePath ${python} -ArgumentList ${server}
Start-Sleep -Seconds 3
Write-Host "Server: http://127.0.0.1:5001" -ForegroundColor Green
Start-Process "http://127.0.0.1:5001"
