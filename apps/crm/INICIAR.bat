@echo off
setlocal
title VisiQuost
cd /d "%~dp0"

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "BACKEND=%ROOT%\backend"
set "VPY=%BACKEND%\.venv\Scripts\python.exe"

if not exist "%VPY%" (
    echo Ambiente nao instalado. Rodando INSTALAR.bat...
    call "%ROOT%\INSTALAR.bat"
    exit /b
)

REM ---- Descobre IP da LAN pro celular ----
set "LANIP="
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /r /c:"IPv4.*: 192\." /c:"IPv4.*: 10\." /c:"IPv4.*: 172\."') do (
    for /f "tokens=* delims= " %%b in ("%%a") do if not defined LANIP set "LANIP=%%b"
)

echo.
echo ================================================
echo   VisiQuost - servidor local
echo ================================================
echo.
echo   No PC:      http://127.0.0.1:8000/
if defined LANIP echo   No celular: http://%LANIP%:8000/   (mesma Wi-Fi)
echo.
echo   Copie a URL acima e cole no seu navegador.
echo   Para parar: feche esta janela (ou Ctrl+C aqui).
echo ================================================
echo.

pushd "%BACKEND%"
"%VPY%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
popd
endlocal
