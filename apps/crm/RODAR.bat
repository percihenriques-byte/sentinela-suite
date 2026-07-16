@echo off
title VisiQuost
cd /d "%~dp0"

REM Se venv nao existe -> instala primeiro
if not exist "backend\.venv\Scripts\python.exe" (
    call INSTALAR.bat
    exit /b
)

REM Ja instalado -> inicia
call INICIAR.bat
