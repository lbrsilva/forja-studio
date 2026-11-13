@echo off
rem ============================================================================
rem  Cria o icone "Forja Studio" na sua Area de Trabalho.
rem
rem  Para que isto existe: ate 12/11/2026 o icone so nascia DURANTE a instalacao,
rem  e so se a pessoa respondesse uma pergunta na janela preta. Quem instalou pelo
rem  GitHub, quem fechou a janela antes da pergunta, ou quem rodou o instalador de
rem  um jeito que nao consegue perguntar ficava sem icone - e sem saber por que.
rem
rem  Agora da para pedir o icone quando quiser: e so clicar neste arquivo.
rem  Pode clicar quantas vezes quiser: ele refaz o mesmo icone, nao duplica.
rem
rem  Nao termina com "exit": se der errado, a janela FICA aberta mostrando o motivo.
rem ============================================================================
chcp 65001 >nul
title Forja Studio - criar o icone
cd /d "%~dp0"

rem Pelo caminho ABSOLUTO: "caminhos.bat" sozinho depende da pasta atual, e ha
rem ambiente de Windows que recusa rodar arquivo da pasta atual
rem (NoDefaultCurrentDirectoryInExePath=1). Com %~dp0 nao depende de nada.
if exist "%~dp0caminhos.bat" call "%~dp0caminhos.bat"

rem O Python da ComfyUI, quando existe. Quem instalou so o painel (sem a ComfyUI)
rem ainda nao tem essa pasta - ai vale o Python do proprio Windows.
set "PY=ComfyUI_windows_portable\python_embeded\python.exe"
if not exist "%PY%" set "PY=py -3"

echo.
echo   Criando o icone do Forja Studio na Area de Trabalho...
echo.
%PY% "estudio\atalho.py"
if errorlevel 1 goto deuerrado

echo.
echo   Pronto. Procure o icone "Forja Studio" na sua Area de Trabalho.
echo   Clicar nele abre SO a pagina: nenhuma janela preta e nenhuma IA ligada.
echo.
pause
goto :eof

:deuerrado
echo.
echo   Nao deu para criar o icone - o motivo esta escrito logo acima.
echo   Enquanto isso, da para abrir o estudio pelo "Forja Studio.bat",
echo   aqui nesta mesma pasta.
echo.
pause
