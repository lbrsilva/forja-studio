@echo off
chcp 65001 >nul
title Desligar a abertura automatica
echo.
echo   Isto faz o Forja Studio NAO abrir mais sozinho com o Windows.
echo   O atalho "Forja Studio.bat" continua funcionando normalmente.
echo.
schtasks /delete /tn "Forja Studio" /f
if errorlevel 1 (
  echo.
  echo   Nao achei a abertura automatica - ou ela nunca foi criada,
  echo   ou falta permissao (tente como administrador).
)
echo.
pause
