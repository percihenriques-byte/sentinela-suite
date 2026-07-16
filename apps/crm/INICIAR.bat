@echo off
setlocal
title VisiQuost
cd /d "%~dp0"

set "VPY=backend\.venv\Scripts\pythonw.exe"
set "VPY_CONSOLE=backend\.venv\Scripts\python.exe"

if not exist "%VPY_CONSOLE%" (
    echo Ambiente nao instalado. Rodando INSTALAR.bat...
    call INSTALAR.bat
    exit /b
)

REM Garante que pywebview esta instalado (pra quem tem venv antigo)
"%VPY_CONSOLE%" -c "import webview" 2>nul
if errorlevel 1 (
    echo Instalando pywebview...
    "%VPY_CONSOLE%" -m pip install pywebview --quiet --disable-pip-version-check
)

REM Usa pythonw.exe (sem janela de console) se disponivel, senao python.exe
if not exist "%VPY%" set "VPY=%VPY_CONSOLE%"

REM Abre o app desktop (janela WebView2). Server sobe internamente.
pushd backend
start "" "..\%VPY%" desktop.py
popd
endlocal
