<#
    Sentinela-Guardiao.ps1
    ------------------------------------------------------------------
    O "guardiao" e o que torna a protecao dificil de burlar: uma tarefa
    agendada roda este script a cada 1 minuto. Se o estado diz que o
    Sentinela deve estar ATIVO, mas alguem removeu o bloco hosts ou
    trocou o DNS, o guardiao REAPLICA a protecao na hora.

    Assim, "desligar mexendo nas configuracoes" nao adianta: em ate
    1 minuto tudo volta. O unico jeito de desligar de verdade e pelo
    Desativar-Sentinela.ps1, que pede o PIN.
    ------------------------------------------------------------------
#>
param([switch]$Simular)

. (Join-Path $PSScriptRoot 'Sentinela-Core.ps1')

if ($Simular) { $env:SENTINELA_SIMULAR = '1' }

$state = Get-SentinelaState
if (-not $state.ativo) {
    # protecao esta desligada oficialmente (via PIN). Nada a fazer.
    return
}

$reaplicou = $false

if (-not (Test-SentinelaHostsApplied)) {
    Set-SentinelaHosts -Simular:$Simular
    Write-SentinelaLog 'GUARDIAO: bloco hosts havia sido removido - reaplicado.' 'WARN'
    $reaplicou = $true
}

if (-not (Test-SentinelaDnsApplied)) {
    Set-SentinelaDns -Simular:$Simular
    Write-SentinelaLog 'GUARDIAO: DNS de filtro havia sido trocado - reaplicado.' 'WARN'
    $reaplicou = $true
}

if (-not (Test-SentinelaSafeSearchApplied)) {
    Set-SentinelaSafeSearch -Simular:$Simular
    Write-SentinelaLog 'GUARDIAO: politicas de SafeSearch do navegador haviam sido removidas - reaplicadas.' 'WARN'
    $reaplicou = $true
}

if ($reaplicou) {
    Write-Host 'Guardiao reaplicou a protecao do Sentinela.' -ForegroundColor Yellow
} else {
    Write-SentinelaLog 'GUARDIAO: verificacao OK, protecao intacta.' 'INFO'
}
