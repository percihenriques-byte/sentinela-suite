@echo off
setlocal
title Sentinela Suite - Instalador
cd /d "%~dp0"

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "CRM=%ROOT%\apps\crm"

if not exist "%CRM%\INSTALAR.bat" (
    echo ERRO: nao achei "%CRM%\INSTALAR.bat"
    echo Este .bat deve ficar na raiz do monorepo da Sentinela Suite.
    pause
    exit /b 1
)

echo.
echo ================================================
echo   SENTINELA SUITE - Instalador
echo ================================================
echo.
echo   Vou instalar o servidor local, que serve:
echo     - o CRM (VisiQuost)
echo     - o painel do responsavel (Sentinela)
echo.
echo   A protecao do PC da familia (DNS + hosts + politica
echo   do navegador) e instalada a parte, porque pede
echo   permissao de administrador:
echo.
echo       apps\guardian\app\INSTALAR.bat
echo.
echo ================================================
echo.

REM O instalador do CRM ja detecta/instala Python, cria a venv, aplica
REM migrations, popula os dados demo e sobe o servidor. Nao duplicamos
REM essa logica aqui: um instalador so, um lugar so para consertar.
call "%CRM%\INSTALAR.bat"
endlocal
exit /b 0
