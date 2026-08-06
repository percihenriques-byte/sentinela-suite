<#
    Sentinela-Status.ps1
    Mostra a situacao atual da protecao (para o responsavel conferir).
    Uso: .\Sentinela-Status.ps1 [-Simular]
#>
param([switch]$Simular)

. (Join-Path $PSScriptRoot 'Sentinela-Core.ps1')
. (Join-Path $PSScriptRoot 'Sentinela-Pin.ps1')

if ($Simular) { $env:SENTINELA_SIMULAR = '1' }

$s = Get-SentinelaStatus
Write-Host ''
Write-Host '  === SENTINELA ===' -ForegroundColor Cyan
$cor = if ($s.Ativo) { 'Green' } else { 'Red' }
Write-Host ('  Estado........: ' + $(if ($s.Ativo) { 'ATIVO' } else { 'DESLIGADO' })) -ForegroundColor $cor
Write-Host ('  DNS de filtro.: ' + $(if ($s.DnsAplicado) { 'aplicado' } else { 'ausente' }))
Write-Host ('  Bloco hosts...: ' + $(if ($s.HostsAplicado) { 'aplicado' } else { 'ausente' }))
Write-Host ('  PIN definido..: ' + $(if (Test-SentinelaPinConfigured) { 'sim' } else { 'NAO' }))
if ($s.Desde) { Write-Host ('  Desde.........: ' + $s.Desde) }
if ($s.Simulacao) { Write-Host '  (modo simulacao - nada real foi alterado)' -ForegroundColor Yellow }
Write-Host ''
