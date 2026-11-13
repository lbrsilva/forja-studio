@echo off
rem  Versao sem janela, usada pela abertura automatica do Windows.
rem  Liga o estudio e NAO abre navegador: quem acabou de entrar no Windows nao
rem  quer uma aba pulando na cara. A pagina fica esperando em 127.0.0.1:8194.
cd /d "%~dp0"
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
if not defined PY exit /b 1
powershell -NoProfile -Command "try{$null=Invoke-WebRequest 'http://127.0.0.1:8194/api/ocupado' -UseBasicParsing -TimeoutSec 3;exit 0}catch{exit 1}"
if not errorlevel 1 exit /b 0
start "Forja Studio" /min "%PY%" -s "estudio\server.py"
