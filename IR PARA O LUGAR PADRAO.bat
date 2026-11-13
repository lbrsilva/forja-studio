@echo off
rem ============================================================================
rem  Leva esta instalacao para o lugar padrao: C:\ForjaStudio
rem
rem  Por que existe um lugar padrao (ver INSTALAR.md):
rem    - sem espaco no nome: caminho com espaco ja quebrou .bat neste projeto;
rem    - fora do Documentos: em muita maquina o OneDrive sincroniza o Documentos,
rem      e tentaria subir os 270 GB de modelos;
rem    - curto: o Windows corta caminho em 260 caracteres.
rem
rem  Ele COPIA e nao move: o original fica ate voce conferir. E so faz isso numa
rem  instalacao LEVE - se a ComfyUI ja estiver dentro, ele recusa e explica.
rem
rem  Nao termina com "exit": se der errado, a janela FICA aberta com o motivo.
rem ============================================================================
chcp 65001 >nul
title Forja Studio - ir para o lugar padrao
cd /d "%~dp0"

set "DESTINO=C:\ForjaStudio"
rem (so para teste: passar outro destino como primeiro argumento)
if not "%~1"=="" set "DESTINO=%~1"

echo.
echo   De : %CD%
echo   Para: %DESTINO%
echo.

if /i "%CD%"=="%DESTINO%" (
  echo   Voce JA esta no lugar padrao. Nao ha nada a fazer.
  echo.
  pause
  goto :eof
)

rem --- trava 1: a pasta de destino nao pode ter coisa dentro ---
if exist "%DESTINO%\*" (
  echo   A pasta %DESTINO% JA EXISTE e tem coisa dentro.
  echo.
  echo   Nao vou escrever por cima da pasta de ninguem. Se aquela instalacao
  echo   nao serve mais, apague ou renomeie a pasta e clique aqui de novo.
  echo.
  pause
  goto :eof
)

rem --- trava 2: instalacao pesada nao se copia as cegas ---
echo   Medindo o tamanho desta pasta...
set "TAMANHO=0"
rem SEM PIPE, de proposito: o "|" dentro de for /f num .bat nao sobrevive ao
rem escape, e a conta voltava 0 - ou seja, a trava de tamanho nao travava nada.
rem Medido em 12/11/2026 com um arquivo de 600 MB: com pipe dava 0, assim da 600.
for /f "delims=" %%T in ('powershell -NoProfile -Command "$t=0; foreach($f in (Get-ChildItem -LiteralPath '%CD%' -Recurse -File -Force -EA SilentlyContinue)){$t+=$f.Length}; [int]($t/1MB)"') do set "TAMANHO=%%T"
echo   Tamanho: %TAMANHO% MB

if %TAMANHO% GTR 500 (
  echo.
  echo   Esta instalacao pesa %TAMANHO% MB - a ComfyUI e os modelos ja estao aqui dentro.
  echo.
  echo   Copiar isso tudo levaria muito tempo e dobraria o espaco em disco, entao
  echo   nao vou fazer por conta propria. Faca assim, na mao:
  echo.
  echo     1. feche o estudio ^(clique em "Desligar o estudio.bat"^);
  echo     2. mova esta pasta inteira para %DESTINO%;
  echo     3. la dentro, clique em "Criar o icone na Area de Trabalho.bat".
  echo.
  pause
  goto :eof
)

echo.
echo   Vou COPIAR esta pasta para %DESTINO%.
echo   O original fica aqui, intacto, para voce conferir e apagar depois.
echo.
set /p RESPOSTA=  Pode ir? (S/n):
if /i "%RESPOSTA%"=="n" (
  echo   Tudo bem, nada foi copiado.
  pause
  goto :eof
)

echo.
robocopy "%CD%" "%DESTINO%" /E /NFL /NDL /NJH /NJS /R:1 /W:1
rem o robocopy usa 0-7 para sucesso; 8 ou mais e erro de verdade
if errorlevel 8 (
  echo.
  echo   A copia falhou. Nada foi apagado: a sua pasta continua aqui, inteira.
  echo.
  pause
  goto :eof
)

echo.
echo   Copiado. Refazendo o icone para apontar para o lugar novo...
pushd "%DESTINO%"
call "Criar o icone na Area de Trabalho.bat" >nul 2>&1
popd

echo.
echo   ============================================================
echo    Pronto. O Forja Studio agora esta em %DESTINO%
echo   ============================================================
echo.
echo   O que fazer agora:
echo     1. abra %DESTINO% e confira que esta tudo la;
echo     2. clique no icone "Forja Studio" da Area de Trabalho;
echo     3. funcionando, apague esta pasta antiga:
echo        %CD%
echo.
echo   A pasta antiga NAO foi apagada de proposito. Apague voce, depois de ver
echo   funcionando - e muito pior perder arquivo do que ter pasta sobrando.
echo.
pause
