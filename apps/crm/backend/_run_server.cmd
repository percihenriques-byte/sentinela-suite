@echo off
REM Auxiliar interno chamado pelos .bat do topo. Nao clique diretamente.
title VisiQuost Server
cd /d "%~dp0"
echo Iniciando VisiQuost em 0.0.0.0:8000 (LAN)
echo   PC:      http://127.0.0.1:8000/
echo   Celular: pegue o IP do PC na mesma rede Wi-Fi
echo.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
echo.
echo Servidor parou. Pressione qualquer tecla para fechar.
pause >nul
