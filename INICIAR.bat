@echo off
setlocal
title VisiQuost
cd /d "%~dp0"

set "VPY=backend\.venv\Scripts\python.exe"
if not exist "%VPY%" (
    echo Ambiente nao instalado. Rodando INSTALAR.bat...
    call INSTALAR.bat
    exit /b
)

set "PORT=8000"
set "URL=http://127.0.0.1:%PORT%/"

REM ---- Verifica se ja tem outro VisiQuost rodando na porta ----
powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri '%URL%healthz' -TimeoutSec 1 -UseBasicParsing).StatusCode } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 (
    echo VisiQuost ja esta rodando em %URL%
    start "" "%URL%"
    exit /b 0
)

echo Iniciando VisiQuost em %URL% ...
echo (Servidor em nova janela - feche-a para parar o VisiQuost)
echo.

REM ---- Sobe o servidor em outra janela ----
start "VisiQuost Server" cmd /k "cd /d ""%~dp0backend"" && ""..\%VPY%"" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%"

REM ---- Aguarda health check (max 30s) ----
echo Aguardando servidor iniciar...
set "TRIES=0"
:WAIT
set /a TRIES+=1
powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri '%URL%healthz' -TimeoutSec 1 -UseBasicParsing).StatusCode } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 goto READY
if %TRIES% GEQ 30 goto TIMEOUT
timeout /t 1 /nobreak >nul
goto WAIT

:READY
echo Servidor pronto. Abrindo navegador...
start "" "%URL%"
echo.
echo VisiQuost rodando em %URL%
echo Feche esta janela quando quiser (o servidor continua na outra).
timeout /t 5 /nobreak >nul
exit /b 0

:TIMEOUT
echo.
echo AVISO: Servidor demorou mais de 30s para iniciar.
echo Verifique a janela "VisiQuost Server" para ver erros.
echo Se o server esta rodando, abra manualmente: %URL%
pause
exit /b 1
