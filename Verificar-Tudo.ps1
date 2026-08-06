<#
    Verificar-Tudo.ps1
    ------------------------------------------------------------------
    O portao unico da suite: roda TODAS as verificacoes, na ordem, e falha
    alto na primeira que quebrar.

    E a mesma lista que o CI executa (.github/workflows/ci.yml). Ter os dois
    apontando para as mesmas suites e de proposito: enquanto o workflow nao
    estiver publicado, isto aqui ja da a garantia; depois de publicado,
    continua sendo como rodar o CI na sua maquina antes de empurrar.

    Uso:
        .\Verificar-Tudo.ps1              # tudo (~5 min)
        .\Verificar-Tudo.ps1 -Rapido      # so o que roda em segundos
        .\Verificar-Tudo.ps1 -SemE2E      # pula o que abre navegador
    ------------------------------------------------------------------
#>
param(
    [switch]$Rapido,
    [switch]$SemE2E
)

$ErrorActionPreference = 'Continue'
$raiz = $PSScriptRoot
$py = Join-Path $raiz 'apps\crm\backend\.venv\Scripts\python.exe'

if (-not (Test-Path $py)) {
    Write-Host ''
    Write-Host '  Ambiente nao instalado. Rode INSTALAR.bat primeiro.' -ForegroundColor Red
    Write-Host ''
    exit 1
}

$resultados = @()
$inicioTudo = Get-Date

function Invoke-Etapa {
    param(
        [Parameter(Mandatory)][string]$Nome,
        [Parameter(Mandatory)][scriptblock]$Acao
    )
    Write-Host ''
    Write-Host ("  > {0}" -f $Nome) -ForegroundColor Cyan
    $inicio = Get-Date
    $saida = & $Acao 2>&1
    $ok = ($LASTEXITCODE -eq 0)
    $seg = [math]::Round(((Get-Date) - $inicio).TotalSeconds, 1)

    foreach ($l in @($saida | Select-Object -Last 4)) {
        Write-Host ("    {0}" -f $l) -ForegroundColor DarkGray
    }

    if ($ok) {
        Write-Host ("    [OK] {0}s" -f $seg) -ForegroundColor Green
    } else {
        Write-Host ("    [FALHOU] {0}s" -f $seg) -ForegroundColor Red
        # Em falha, mostra bem mais contexto: quem roda isto quer consertar.
        Write-Host ''
        Write-Host '    --- saida completa ---' -ForegroundColor DarkYellow
        $saida | Select-Object -Last 40 | ForEach-Object { Write-Host ("    {0}" -f $_) }
    }
    $script:resultados += [pscustomobject]@{ Nome = $Nome; Ok = $ok; Segundos = $seg }
}

Write-Host ''
Write-Host '  ================================================' -ForegroundColor Cyan
Write-Host '   SENTINELA SUITE - verificacao completa' -ForegroundColor Cyan
Write-Host '  ================================================'

# --- 1. Paridade dos classificadores (segundos, e o mais critico) ---
Invoke-Etapa 'Paridade PS <-> JS do classificador' {
    Push-Location (Join-Path $raiz 'apps\crm\backend')
    & $py -m pytest tests/test_classificador_paridade.py -q
    Pop-Location
}

# --- 2. Regressoes das auditorias ---
Invoke-Etapa 'Achados de auditoria (A* e B*)' {
    Push-Location (Join-Path $raiz 'apps\crm\backend')
    & $py -m pytest tests/test_auditoria.py -q
    Pop-Location
}

if ($Rapido) {
    Write-Host ''
    Write-Host '  (-Rapido: parando aqui)' -ForegroundColor DarkGray
} else {
    # --- 3. Suite completa da API ---
    Invoke-Etapa 'API + CRM (pytest completo)' {
        Push-Location (Join-Path $raiz 'apps\crm\backend')
        & $py -m pytest -q
        Pop-Location
    }

    # --- 4. Migrations em banco limpo ---
    Invoke-Etapa 'Migrations (up / down / up)' {
        Push-Location (Join-Path $raiz 'apps\crm\backend')
        $tmp = Join-Path $env:TEMP ("sentinela-mig-{0}.db" -f [guid]::NewGuid())
        $env:DATABASE_URL = 'sqlite:///' + ($tmp -replace '\\', '/')
        $env:APP_SECRET_KEY = 'verificacao-local'
        $env:FIELD_ENCRYPTION_KEY = 'verificacao-local'
        & $py -m alembic upgrade head *> $null
        $a = $LASTEXITCODE
        & $py -m alembic downgrade base *> $null
        $b = $LASTEXITCODE
        & $py -m alembic upgrade head *> $null
        $c = $LASTEXITCODE
        Remove-Item $tmp -ErrorAction SilentlyContinue
        Remove-Item Env:\DATABASE_URL, Env:\APP_SECRET_KEY, Env:\FIELD_ENCRYPTION_KEY -ErrorAction SilentlyContinue
        Pop-Location
        if ($a -eq 0 -and $b -eq 0 -and $c -eq 0) { 'ciclo completo ok'; $global:LASTEXITCODE = 0 }
        else { 'ciclo falhou'; $global:LASTEXITCODE = 1 }
    }

    # --- 5. Classificador (PowerShell) ---
    Invoke-Etapa 'Classificador - suite de 139 testes' {
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $raiz 'apps\guardian\app\Testes\Executar-Testes.ps1')
    }

    Invoke-Etapa 'Classificador - corpus rotulado (motor PowerShell)' {
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $raiz 'apps\guardian\app\Testes\Medir-Precisao.ps1')
    }

    if (-not $SemE2E) {
        # --- 6. O corpus no motor que roda no navegador da crianca ---
        Invoke-Etapa 'Corpus rotulado no motor JS (navegador)' {
            & $py (Join-Path $raiz 'apps\guardian\app\Testes\Testar-Paridade.py')
        }

        # --- 7. E2E ---
        Invoke-Etapa 'E2E - extensao + ponte PowerShell' {
            & $py (Join-Path $raiz 'apps\guardian\app\Testes\Testar-Sync.py')
        }

        Invoke-Etapa 'E2E - painel na SPA' {
            & $py (Join-Path $raiz 'apps\guardian\app\Testes\Testar-Painel.py')
        }
    } else {
        Write-Host ''
        Write-Host '  (-SemE2E: pulando o que abre navegador)' -ForegroundColor DarkGray
    }
}

# --- Resumo ---
$totalSeg = [math]::Round(((Get-Date) - $inicioTudo).TotalSeconds, 1)
$falhas = @($resultados | Where-Object { -not $_.Ok })

Write-Host ''
Write-Host '  ================================================'
foreach ($r in $resultados) {
    $marca = if ($r.Ok) { '[OK]    ' } else { '[FALHOU]' }
    $cor = if ($r.Ok) { 'Green' } else { 'Red' }
    Write-Host ("   {0} {1,-46} {2,6}s" -f $marca, $r.Nome, $r.Segundos) -ForegroundColor $cor
}
Write-Host '  ================================================'

if ($falhas.Count -eq 0) {
    Write-Host ("   TUDO VERDE - {0} etapas em {1}s" -f $resultados.Count, $totalSeg) -ForegroundColor Green
    Write-Host ''
    exit 0
}

Write-Host ("   {0} de {1} etapas FALHARAM ({2}s)" -f $falhas.Count, $resultados.Count, $totalSeg) -ForegroundColor Red
Write-Host ''
exit 1
