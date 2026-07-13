@echo off
title Instalar Sentinela
echo.
echo   Iniciando o instalador do Sentinela...
echo   (uma janela vai pedir permissao de Administrador - clique em SIM)
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Instalar-Sentinela.ps1"
