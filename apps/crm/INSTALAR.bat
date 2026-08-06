@echo off
setlocal enabledelayedexpansion
title VisiQuost - Instalador

REM ---- Todos os paths sao ABSOLUTOS baseados em %~dp0 (dir do proprio .bat) ----
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "BACKEND=%ROOT%\backend"
set "REQ=%BACKEND%\requirements.txt"
set "VENV=%BACKEND%\.venv"
set "VPY=%VENV%\Scripts\python.exe"
set "ENV_FILE=%BACKEND%\.env"
set "ENV_EXAMPLE=%BACKEND%\.env.example"

REM Sanidade: confirma que estamos no lugar certo
if not exist "%REQ%" (
    echo ERRO: nao achei "%REQ%"
    echo Este .bat deve estar na raiz do projeto visiquost-crm.
    echo Certifique que a pasta backend\ existe ao lado deste arquivo.
    pause
    exit /b 1
)

cd /d "%ROOT%"

echo.
echo ========================================
echo   VisiQuost - Instalador
echo ========================================
echo.
echo Este instalador cuida de tudo sozinho:
echo   * Detecta ou instala Python 3.12
echo   * Cria ambiente virtual e dependencias
echo   * Prepara o banco de dados e dados demo
echo   * Sobe o servidor
echo.

REM ---- [1/6] Localiza Python (py launcher > python no PATH) ----
set "PYEXE="
where py >nul 2>&1
if not errorlevel 1 set "PYEXE=py -3"
if not defined PYEXE (
    where python >nul 2>&1
    if not errorlevel 1 set "PYEXE=python"
)

if not defined PYEXE (
    echo [1/6] Python nao encontrado. Tentando via winget...
    where winget >nul 2>&1
    if errorlevel 1 (
        echo ERRO: winget nao disponivel. Baixe Python em https://python.org/downloads/
        pause & exit /b 1
    )
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements --silent
    if errorlevel 1 (
        echo Falha ao instalar Python via winget. Baixe manualmente em https://python.org/downloads/
        pause & exit /b 1
    )
    echo Python instalado. Feche esta janela e rode INSTALAR.bat de novo.
    pause & exit /b 0
) else (
    echo [1/6] Python detectado: %PYEXE%
)

REM ---- [2/6] Versao minima 3.10+ ----
echo [2/6] Verificando versao do Python...
%PYEXE% -c "import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)"
if errorlevel 1 (
    echo ERRO: Python 3.10+ necessario.
    pause & exit /b 1
)

REM ---- [3/6] venv ----
if exist "%VENV%" (
    "%VPY%" --version >nul 2>&1
    if errorlevel 1 (
        echo [3/6] venv quebrado, recriando...
        rmdir /s /q "%VENV%"
    )
)
if not exist "%VPY%" (
    echo [3/6] Criando ambiente virtual em "%VENV%"...
    %PYEXE% -m venv "%VENV%"
    if errorlevel 1 (
        echo ERRO ao criar venv.
        pause & exit /b 1
    )
) else (
    echo [3/6] Ambiente virtual OK.
)

REM ---- [4/6] Dependencias ----
echo [4/6] Instalando dependencias (1-2 min)...
"%VPY%" -m pip install --upgrade pip --quiet --disable-pip-version-check
"%VPY%" -m pip install -r "%REQ%" --quiet --disable-pip-version-check
if errorlevel 1 (
    echo.
    echo ERRO ao instalar dependencias. Verifique sua conexao.
    echo Manual: "%VPY%" -m pip install -r "%REQ%"
    pause & exit /b 1
)

REM ---- .env ----
if not exist "%ENV_FILE%" (
    echo    - Criando "%ENV_FILE%" com chaves aleatorias
    copy "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
    for /f "delims=" %%k in ('"%VPY%" -c "import secrets;print(secrets.token_urlsafe(48))"') do set "SECRET=%%k"
    powershell -NoProfile -Command "(Get-Content '%ENV_FILE%') -replace 'APP_SECRET_KEY=.*', 'APP_SECRET_KEY=!SECRET!' | Set-Content '%ENV_FILE%'"
    REM Chave de cifra em repouso do registro de supervisao. Sem ela o app
    REM recusa subir (de proposito): melhor recusar do que gravar texto claro.
    for /f "delims=" %%f in ('"%VPY%" -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"') do set "FERNET=%%f"
    powershell -NoProfile -Command "(Get-Content '%ENV_FILE%') -replace 'FIELD_ENCRYPTION_KEY=.*', 'FIELD_ENCRYPTION_KEY=!FERNET!' | Set-Content '%ENV_FILE%'"
)

REM Instalacao antiga pode ter .env sem a chave de cifra: preenche sem tocar no resto.
"%VPY%" -c "import io,sys;p=r'%ENV_FILE%';t=io.open(p,encoding='utf-8').read();sys.exit(0 if [l for l in t.splitlines() if l.startswith('FIELD_ENCRYPTION_KEY=') and l.split('=',1)[1].strip()] else 1)"
if errorlevel 1 (
    echo    - Preenchendo FIELD_ENCRYPTION_KEY que faltava no .env
    for /f "delims=" %%f in ('"%VPY%" -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"') do set "FERNET2=%%f"
    powershell -NoProfile -Command "$c = Get-Content '%ENV_FILE%'; if ($c -match '^FIELD_ENCRYPTION_KEY=') { $c = $c -replace '^FIELD_ENCRYPTION_KEY=.*', 'FIELD_ENCRYPTION_KEY=!FERNET2!' } else { $c += 'FIELD_ENCRYPTION_KEY=!FERNET2!' }; Set-Content '%ENV_FILE%' $c"
)

REM ---- [5/6] Migrations + seed ----
echo [5/6] Aplicando migrations...
pushd "%BACKEND%"
"%VPY%" -m alembic upgrade head
if errorlevel 1 (
    echo ERRO em alembic upgrade. Apague "%BACKEND%\jarvis_crm.db" e reinstale.
    popd & pause & exit /b 1
)
REM Em producao o bootstrap nao cria conta nenhuma: a conta demo tem senha
REM fixa e nao entra em instalacao real. O responsavel cria a conta dele no
REM primeiro acesso, pela propria tela do app.
"%VPY%" scripts\bootstrap.py
if errorlevel 1 (
    echo AVISO: bootstrap falhou -- nao critico, voce ainda pode usar o app
)
popd

REM ---- Pasta de trabalho ----
if not exist "%USERPROFILE%\Documents\VisiQuost" (
    echo    - Criando "%USERPROFILE%\Documents\VisiQuost"
    mkdir "%USERPROFILE%\Documents\VisiQuost" 2>nul
)

REM ---- [6/6] Health check import ----
echo [6/6] Verificando saude do sistema...
pushd "%BACKEND%"
"%VPY%" -c "from app.main import app; print('   OK: app importa sem erro')"
if errorlevel 1 (
    echo ERRO: modulo app nao carrega.
    popd & pause & exit /b 1
)
popd

echo.
echo ========================================
echo   Instalacao concluida!
echo ========================================
echo.
echo Pasta de trabalho: %USERPROFILE%\Documents\VisiQuost
echo.
echo No primeiro acesso, crie a conta do responsavel na tela do app
echo e defina o PIN em Sentinela -^> PIN do responsavel.
echo.
echo Iniciando servidor...
echo.

endlocal
call "%~dp0INICIAR.bat"
exit /b 0
