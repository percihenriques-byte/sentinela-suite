@echo off
title Travar a extensao do Sentinela
echo.
echo   Vamos travar a extensao para a crianca nao conseguir desativar.
echo   (uma janela vai pedir permissao de Administrador - clique em SIM)
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Travar-Extensao.ps1"
pause
