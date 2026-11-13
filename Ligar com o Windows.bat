@echo off
rem  Faz o Forja Studio subir sozinho quando voce entra no Windows.
rem
rem  O que isto liga e SO o estudio - o programa leve que serve a pagina. Ele NAO
rem  liga a ComfyUI nem carrega modelo nenhum: a placa de video so e usada quando
rem  voce aperta "Ligar" na tela. Gasta uns 50 MB de memoria parado.
rem
rem  Para desfazer, use "Nao ligar com o Windows.bat".
chcp 65001 >nul
title Ligar o Forja Studio com o Windows
cd /d "%~dp0"

echo.
echo   Isto faz o Forja Studio abrir sozinho toda vez que voce entra no Windows.
echo   So o estudio (a pagina). A placa de video continua so ligando quando voce pedir.
echo.
set /p OK="  Pode criar? (s/N): "
if /i not "%OK%"=="s" goto fim

schtasks /create /tn "Forja Studio" /tr "\"%CD%\Forja Studio - silencioso.bat\"" /sc onlogon /delay 0000:30 /f
if errorlevel 1 (
  echo.
  echo   Nao consegui criar. Quase sempre e falta de permissao:
  echo   feche esta janela, clique com o botao DIREITO neste arquivo
  echo   e escolha "Executar como administrador".
  echo.
  pause
  exit /b 1
)
echo.
echo   Pronto. Da proxima vez que ligar o PC, a pagina ja vai estar de pe em
echo   http://127.0.0.1:8194 - e voce liga a IA pelos botoes da tela.
echo.
:fim
pause
