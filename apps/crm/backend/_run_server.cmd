@echo off
REM Auxiliar interno chamado pelos .bat do topo. Nao clique diretamente.
title Sentinela Server
cd /d "%~dp0"
REM Loopback por padrao. SENTINELA_BIND_LAN=1 abre para a rede (ver INICIAR.bat).
set "BIND=127.0.0.1"
if "%SENTINELA_BIND_LAN%"=="1" set "BIND=0.0.0.0"
echo Iniciando Sentinela em %BIND%:8000
echo   PC: http://127.0.0.1:8000/
echo.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host %BIND% --port 8000
echo.
echo Servidor parou. Pressione qualquer tecla para fechar.
pause >nul
