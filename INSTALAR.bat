@echo off
setlocal enabledelayedexpansion
title VisiQuost - Instalador

cd /d "%~dp0"

echo.
echo ========================================
echo   VisiQuost - Instalador
echo ========================================
echo.
echo Este instalador cuida de tudo sozinho:
echo   * Detecta ou instala Python 3.12
echo   * Cria ambiente virtual e dependencias
echo   * Prepara o banco de dados e dados demo
echo   * Sobe o servidor e abre o navegador
echo.

REM ---- [1/6] Localiza Python ----
set "PYEXE="
where py >nul 2>&1 && (for /f "delims=" %%p in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do set "PYEXE=%%p")
if not defined PYEXE (
    where python >nul 2>&1 && (for /f "delims=" %%p in ('python -c "import sys;print(sys.executable)" 2^>nul') do set "PYEXE=%%p")
)

if not defined PYEXE (
    echo [1/6] Python nao encontrado. Tentando via winget...
    where winget >nul 2>&1
    if errorlevel 1 (
        echo.
        echo ERRO: winget nao esta disponivel no sistema.
        echo Baixe Python manualmente em https://python.org/downloads/
        echo Reexecute este INSTALAR.bat depois de instalar.
        echo.
        pause
        exit /b 1
    )
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements --silent
    if errorlevel 1 (
        echo.
        echo Falha ao instalar Python via winget.
        echo Baixe manualmente em https://python.org/downloads/
        pause
        exit /b 1
    )
    echo Python instalado. Feche esta janela e rode INSTALAR.bat de novo
    echo para que o PATH atualize.
    pause
    exit /b 0
) else (
    echo [1/6] Python detectado: %PYEXE%
)

REM ---- [2/6] Verifica versao minima do Python (3.10+) ----
for /f "delims=" %%v in ('"%PYEXE%" -c "import sys;print('%%d.%%d' %% sys.version_info[:2])" 2^>nul') do set "PYVER=%%v"
echo [2/6] Versao Python: %PYVER%
"%PYEXE%" -c "import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python 3.10 ou superior necessario. Instale uma versao mais nova.
    pause
    exit /b 1
)

REM ---- [3/6] Cria/recupera venv ----
set "VENV=backend\.venv"
set "VPY=%VENV%\Scripts\python.exe"

REM Verifica se venv existe mas esta quebrado
if exist "%VENV%" (
    "%VPY%" --version >nul 2>&1
    if errorlevel 1 (
        echo [3/6] venv quebrado detectado. Removendo e recriando...
        rmdir /s /q "%VENV%"
    )
)

if not exist "%VPY%" (
    echo [3/6] Criando ambiente virtual...
    "%PYEXE%" -m venv "%VENV%"
    if errorlevel 1 (
        echo ERRO ao criar venv.
        pause & exit /b 1
    )
) else (
    echo [3/6] Ambiente virtual OK.
)

REM ---- [4/6] Instala dependencias ----
echo [4/6] Instalando dependencias (1-2 min)...
"%VPY%" -m pip install --upgrade pip --quiet --disable-pip-version-check
"%VPY%" -m pip install -r backend\requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 (
    echo.
    echo ERRO ao instalar dependencias. Verifique sua conexao com a internet.
    echo Tente rodar manualmente: %VPY% -m pip install -r backend\requirements.txt
    pause & exit /b 1
)

REM ---- Cria .env se faltar ----
if not exist "backend\.env" (
    echo    - Criando backend\.env com chave secreta aleatoria
    copy backend\.env.example backend\.env >nul
    for /f "delims=" %%k in ('"%VPY%" -c "import secrets;print(secrets.token_urlsafe(48))"') do set "SECRET=%%k"
    powershell -NoProfile -Command "(Get-Content backend\.env) -replace 'APP_SECRET_KEY=.*', 'APP_SECRET_KEY=!SECRET!' | Set-Content backend\.env"
)

REM ---- [5/6] Migrations + seed ----
echo [5/6] Aplicando migrations + populando dados demo...
pushd backend
"%VPY%" -m alembic upgrade head
if errorlevel 1 (
    echo ERRO em alembic upgrade. O banco pode estar corrompido.
    echo Solucao: apague backend\db.sqlite e rode INSTALAR.bat de novo.
    popd & pause & exit /b 1
)
"%VPY%" scripts\bootstrap.py
if errorlevel 1 (
    echo AVISO: bootstrap falhou (nao critico) — voce ainda pode usar o app.
)
popd

REM ---- Cria pasta de trabalho ----
if not exist "%USERPROFILE%\Documents\VisiQuost" (
    echo    - Criando pasta de trabalho: %USERPROFILE%\Documents\VisiQuost
    mkdir "%USERPROFILE%\Documents\VisiQuost" 2>nul
)

REM ---- [6/6] Health check antes de subir servidor ----
echo [6/6] Verificando saude do sistema...
pushd backend
"%VPY%" -c "from app.main import app; print('   OK: app importa sem erro')" 2>nul
if errorlevel 1 (
    echo ERRO: modulo app nao carrega. Reinstale as dependencias.
    popd & pause & exit /b 1
)
popd

REM ---- Sobe servidor + abre navegador ----
echo.
echo ========================================
echo   Instalacao concluida!
echo ========================================
echo.
echo Servidor: http://127.0.0.1:8000/
echo Pasta de trabalho: %USERPROFILE%\Documents\VisiQuost
echo.
echo Feche esta janela para parar o servidor.
echo.
timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:8000/"
pushd backend
"%VPY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
popd

endlocal
