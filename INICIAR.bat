@echo off
setlocal
title Sentinela Suite
cd /d "%~dp0"

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "CRM=%ROOT%\apps\crm"
set "VPY=%CRM%\backend\.venv\Scripts\python.exe"

if not exist "%VPY%" (
    echo Ambiente nao instalado. Rodando INSTALAR.bat...
    call "%ROOT%\INSTALAR.bat"
    exit /b
)

REM ---- Rede: loopback por padrao ----
REM O painel guarda o historico de navegacao de uma crianca. Abrir isso para
REM toda a Wi-Fi por conveniencia nao vale o risco: em rede de predio, escola
REM ou cafe, "rede local" inclui estranhos. Quem quiser mesmo abrir no celular
REM roda:  set SENTINELA_BIND_LAN=1  antes deste .bat, ciente de que a defesa
REM passa a ser so a senha do responsavel.
set "BIND=127.0.0.1"
set "LANIP="
if "%SENTINELA_BIND_LAN%"=="1" (
    set "BIND=0.0.0.0"
    for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /r /c:"IPv4.*: 192\." /c:"IPv4.*: 10\." /c:"IPv4.*: 172\."') do (
        for /f "tokens=* delims= " %%b in ("%%a") do if not defined LANIP set "LANIP=%%b"
    )
)

echo.
echo ================================================
echo   SENTINELA SUITE - servidor local
echo ================================================
echo.
echo   No PC:      http://127.0.0.1:8000/
if defined LANIP echo   No celular: http://%LANIP%:8000/   (mesma Wi-Fi)
if not defined LANIP echo   So neste computador. Para abrir na rede: set SENTINELA_BIND_LAN=1
echo.
echo   Dentro do app voce encontra:
echo     - CRM (VisiQuost): contatos, pipeline, Jarvis local
echo     - Sentinela: painel do responsavel (controle parental)
echo.
echo   Para proteger o PC da familia, rode tambem:
echo     apps\guardian\app\INSTALAR.bat
echo.
echo   Para parar: feche esta janela (ou Ctrl+C aqui).
echo ================================================
echo.

pushd "%CRM%\backend"
"%VPY%" -m uvicorn app.main:app --host %BIND% --port 8000
popd
endlocal
