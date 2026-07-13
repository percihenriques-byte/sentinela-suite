<#
    Desativar-Sentinela.ps1
    Desliga a protecao - SO com o PIN do responsavel.
    Uso:
        .\Desativar-Sentinela.ps1
        .\Desativar-Sentinela.ps1 -Simular
#>
param([switch]$Simular)

. (Join-Path $PSScriptRoot 'Sentinela-Core.ps1')
. (Join-Path $PSScriptRoot 'Sentinela-Pin.ps1')

if ($Simular) { $env:SENTINELA_SIMULAR = '1' }

if (-not $Simular -and $env:SENTINELA_SIMULAR -ne '1') {
    $ident = [Security.Principal.WindowsIdentity]::GetCurrent()
    $princ = New-Object Security.Principal.WindowsPrincipal($ident)
    if (-not $princ.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Host 'Este comando precisa ser executado como Administrador.' -ForegroundColor Red
        exit 1
    }
}

Write-Host ''
Write-Host '  Desligar o Sentinela exige o PIN do responsavel.' -ForegroundColor Yellow
if (-not (Request-SentinelaPin -Prompt 'PIN do responsavel')) {
    Write-Host ''
    Write-Host '  Acesso negado. O Sentinela continua ATIVO.' -ForegroundColor Red
    Write-SentinelaLog 'Tentativa de desativar bloqueada: PIN incorreto (esgotou tentativas).' 'WARN'
    exit 1
}

Disable-Sentinela -Simular:$Simular
Write-Host ''
Write-Host '  Sentinela DESATIVADO pelo responsavel.' -ForegroundColor Green
