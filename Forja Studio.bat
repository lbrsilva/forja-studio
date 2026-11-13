@echo off
rem ============================================================================
rem  JerS - Forja Studio: o botao de abrir.
rem
rem  Faz tres coisas, nesta ordem:
rem   1. se o estudio JA estiver no ar, so abre o navegador (nao liga em dobro);
rem   2. senao, liga o estudio e espera ele responder de verdade;
rem   3. so entao abre a pagina - para voce nunca ver "nao foi possivel conectar".
rem
rem  Nao termina com "exit": se der errado, a janela FICA aberta mostrando o erro.
rem  Janela que fecha sozinha esconde o problema (aprendido na marra em 16/10/2026).
rem ============================================================================
chcp 65001 >nul
title JerS - Forja Studio
cd /d "%~dp0"

rem caminhos escolhidos na instalacao (setup.py escreve este arquivo)
rem Pelo caminho ABSOLUTO: "caminhos.bat" sozinho depende da pasta atual, e ha
rem ambiente de Windows que recusa rodar arquivo da pasta atual
rem (NoDefaultCurrentDirectoryInExePath=1). Com %~dp0 nao depende de nada.
if exist "%~dp0caminhos.bat" call "%~dp0caminhos.bat"

rem ---------------------------------------------------------------------------
rem  Qual Python roda o painel.
rem
rem  12/11/2026: aqui so havia o Python da ComfyUI, e o pacote NAO instala a ComfyUI
rem  (ver REPOSITORIOS.md). Quem baixava do GitHub clicava neste botao e nao abria
rem  nada. O painel nao precisa da ComfyUI para MOSTRAR a tela - ela e para gerar
rem  imagem e video. Entao: a da ComfyUI primeiro, e qualquer Python depois.
rem ---------------------------------------------------------------------------
set "PY="
rem A ComfyUI escolhida na instalacao pode estar noutro disco: o caminhos.bat guarda
rem ESTUDIO_COMFY_DIR apontando para <algumlugar>\ComfyUI, e o python_embeded fica ao
rem lado dela. Ate 12/11/2026 isto era ignorado e so se olhava a pasta daqui do lado.
if defined ESTUDIO_COMFY_DIR (
  for %%D in ("%ESTUDIO_COMFY_DIR%\..") do set "COMFYBASE=%%~fD"
)
if defined COMFYBASE if exist "%COMFYBASE%\python_embeded\python.exe" set "PY=%COMFYBASE%\python_embeded\python.exe"
if not defined PY if exist "ComfyUI_windows_portable\python_embeded\python.exe" set "PY=ComfyUI_windows_portable\python_embeded\python.exe"
if not defined PY (
  py -3 -c "import sys" >nul 2>&1
  if not errorlevel 1 set "PY=py -3"
)
if not defined PY (
  python -c "import sys" >nul 2>&1
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo.
  echo   Nao achei nenhum Python nesta maquina.
  echo.
  echo   O painel precisa de um Python 3.10 ou mais novo. Baixe em
  echo     https://www.python.org/downloads/
  echo   e marque "Add python.exe to PATH" na primeira tela do instalador.
  echo.
  echo   Se voce tem a ComfyUI noutra pasta, rode o setup.py de novo para
  echo   apontar o caminho dela.
  echo.
  pause
  exit /b 1
)

echo.
echo   Vendo se o estudio ja esta ligado...
powershell -NoProfile -Command "try{$null=Invoke-WebRequest 'http://127.0.0.1:8194/api/ocupado' -UseBasicParsing -TimeoutSec 3;exit 0}catch{exit 1}"
if not errorlevel 1 (
  echo   Ja estava ligado. Abrindo a pagina.
  start "" "http://127.0.0.1:8194"
  ping -n 3 127.0.0.1 >nul
  exit /b 0
)

echo   Ligando o estudio...
start "Forja Studio" /min "%PY%" -s "estudio\server.py"

echo   Esperando ele responder (ate 60 segundos)...
set TENTATIVA=0
:espera
set /a TENTATIVA+=1
ping -n 3 127.0.0.1 >nul
powershell -NoProfile -Command "try{$null=Invoke-WebRequest 'http://127.0.0.1:8194/api/ocupado' -UseBasicParsing -TimeoutSec 3;exit 0}catch{exit 1}"
if not errorlevel 1 goto pronto
if %TENTATIVA% LSS 30 goto espera

echo.
echo   O estudio nao respondeu em 60 segundos.
echo   Olhe a janela "Forja Studio" que abriu minimizada: o erro esta la.
echo.
pause
exit /b 1

:pronto
echo   Pronto. Abrindo http://127.0.0.1:8194
start "" "http://127.0.0.1:8194"
ping -n 3 127.0.0.1 >nul
