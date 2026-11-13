@echo off
chcp 65001 >nul
title Desligar o Forja Studio
echo.
echo   Fechando o estudio e o que ele tiver ligado...
echo.
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name like '%%python%%'\" | Where-Object { $_.CommandLine -like '*estudio\server.py*' -or $_.CommandLine -like '*ComfyUI\main.py*' } | ForEach-Object { Write-Host ('   fechando ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force }"
echo.
echo   Pronto. A placa de video esta livre.
echo.
pause
