<#
    Desinstalar-Sentinela.ps1
    ------------------------------------------------------------------
    Remove o Sentinela por completo. SO com o PIN do responsavel.
      1. Pede o PIN.
      2. Remove a tarefa agendada (Guardiao).
      3. Desliga a protecao (restaura DNS/hosts).
      4. Remove atalhos e arquivos.

    Uso normal:  .\Desinstalar-Sentinela.ps1  (auto-eleva admin)
    Uso dev...:  .\Desinstalar-Sentinela.ps1 -Simular
    ------------------------------------------------------------------
#>
param([switch]$Simular)

$ErrorActionPreference = 'Stop'
$TASK_NAME = 'Sentinela-Guardiao'

if (-not $Simular) {
    $ident = [Security.Principal.WindowsIdentity]::GetCurrent()
    $princ = New-Object Security.Principal.WindowsPrincipal($ident)
    if (-not $princ.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Start-Process powershell.exe -Verb RunAs -ArgumentList @(
            '-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$PSCommandPath`""
        )
        exit
    }
}

if ($Simular) { $env:SENTINELA_SIMULAR = '1' }

$baseData = if ($Simular) { Join-Path $env:TEMP 'SentinelaSim' } else { Join-Path $env:ProgramData 'Sentinela' }
$destApp  = Join-Path $baseData 'app'

. (Join-Path $destApp 'Sentinela-Core.ps1')
. (Join-Path $destApp 'Sentinela-Pin.ps1')

Write-Host ''
Write-Host '  Desinstalar o Sentinela exige o PIN do responsavel.' -ForegroundColor Yellow
if (-not (Request-SentinelaPin -Prompt 'PIN do responsavel')) {
    Write-Host '  Acesso negado. Nada foi removido.' -ForegroundColor Red
    Write-SentinelaLog 'Tentativa de DESINSTALAR bloqueada: PIN incorreto.' 'WARN'
    if (-not $Simular) { Read-Host '  Pressione ENTER para fechar' }
    exit 1
}

Write-Host '  Removendo o Guardiao...' -ForegroundColor White
if (-not $Simular) {
    try { Unregister-ScheduledTask -TaskName $TASK_NAME -Confirm:$false -ErrorAction Stop }
    catch { Write-Host ('  Aviso: ' + $_.Exception.Message) -ForegroundColor Yellow }
}

Write-Host '  Desligando a protecao...' -ForegroundColor White
Disable-Sentinela -Simular:$Simular

Write-Host '  Removendo atalhos...' -ForegroundColor White
if (-not $Simular) {
    $startMenu = Join-Path $env:ProgramData 'Microsoft\Windows\Start Menu\Programs\Sentinela'
    if (Test-Path $startMenu) { Remove-Item $startMenu -Recurse -Force -ErrorAction SilentlyContinue }
}

Write-Host '  Removendo arquivos...' -ForegroundColor White
Write-SentinelaLog 'Sentinela DESINSTALADO pelo responsavel.' 'ACAO'
# apaga a pasta base (config, estado, app). O log vai junto.
if (Test-Path $baseData) {
    # tenta remover; se algo estiver em uso, ignora
    Remove-Item $baseData -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ''
Write-Host '  Sentinela removido. As buscas voltam ao normal.' -ForegroundColor Green
if (-not $Simular) { Read-Host '  Pressione ENTER para fechar' }
