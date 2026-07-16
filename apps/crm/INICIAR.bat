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

echo Iniciando VisiQuost em http://127.0.0.1:8000/
timeout /t 1 /nobreak >nul
start "" "http://127.0.0.1:8000/"
pushd backend
"%VPY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
popd

endlocal
