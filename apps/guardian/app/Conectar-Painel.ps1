<#
    Conectar-Painel.ps1
    ------------------------------------------------------------------
    Liga este computador ao painel do responsavel (o servidor local da
    suite). Depois disso, tudo que o Sentinela classificar aparece no
    painel automaticamente.

    Onde pegar o token: abra o painel no navegador, va em
    Sentinela -> "Conectar dispositivo" e copie o token.

    Uso:
        .\Conectar-Painel.ps1 -Token <token>
        .\Conectar-Painel.ps1 -Token <token> -Url http://127.0.0.1:8000
        .\Conectar-Painel.ps1 -Token <token> -Dispositivo "pc-da-sala"
        .\Conectar-Painel.ps1 -Status          # so mostra a situacao
        .\Conectar-Painel.ps1 -Desligar        # para de enviar
        .\Conectar-Painel.ps1 -EnviarTudo      # manda o historico acumulado
        .\Conectar-Painel.ps1 -Simular         # usa a pasta de teste
    ------------------------------------------------------------------
#>
param(
    [string]$Token,
    [string]$Url = 'http://127.0.0.1:8000',
    [string]$Dispositivo = $env:COMPUTERNAME,
    [switch]$Status,
    [switch]$Desligar,
    [switch]$EnviarTudo,
    [switch]$Simular
)

. (Join-Path $PSScriptRoot 'Sentinela-Core.ps1')
. (Join-Path $PSScriptRoot 'Sentinela-Classificador.ps1')
. (Join-Path $PSScriptRoot 'Sentinela-Supervisao.ps1')
. (Join-Path $PSScriptRoot 'Sentinela-Ponte.ps1')
if ($Simular) { $env:SENTINELA_SIMULAR = '1' }

function Mostrar-Status {
    $s = Get-PainelStatus
    Write-Host ''
    Write-Host '  PAINEL DO RESPONSAVEL' -ForegroundColor Cyan
    Write-Host '  ---------------------'
    Write-Host ("  Endereco:    {0}" -f $s.Url)
    Write-Host ("  Dispositivo: {0}" -f $s.Dispositivo)
    Write-Host ("  Envio:       {0}" -f $(if ($s.Ligado) { 'ligado' } else { 'desligado' })) -ForegroundColor $(if ($s.Ligado) { 'Green' } else { 'DarkGray' })
    Write-Host ("  Token:       {0}" -f $(if ($s.TemToken) { 'configurado' } else { 'FALTANDO' })) -ForegroundColor $(if ($s.TemToken) { 'Green' } else { 'Yellow' })
    Write-Host ("  Painel no ar: {0}" -f $(if ($s.Alcancavel) { 'sim' } else { 'nao responde' })) -ForegroundColor $(if ($s.Alcancavel) { 'Green' } else { 'Yellow' })
    Write-Host ''
}

if ($Status) { Mostrar-Status; return }

if ($Desligar) {
    Set-PainelConfig -Ligado $false | Out-Null
    Write-Host '  Envio ao painel desligado. O registro continua local.' -ForegroundColor Yellow
    Mostrar-Status
    return
}

if ($EnviarTudo) {
    $n = Sync-SupervisaoComPainel
    Write-Host ("  {0} registro(s) enviados ao painel." -f $n) -ForegroundColor Green
    return
}

if (-not $Token) {
    Write-Host ''
    Write-Host '  Falta o token. Abra o painel no navegador, va em' -ForegroundColor Yellow
    Write-Host '  Sentinela -> "Conectar dispositivo" e copie o token.' -ForegroundColor Yellow
    Write-Host ''
    Write-Host '      .\Conectar-Painel.ps1 -Token <token>'
    Write-Host ''
    Mostrar-Status
    exit 1
}

try {
    Set-PainelConfig -Url $Url -Token $Token -Dispositivo $Dispositivo -Ligado $true | Out-Null
} catch {
    Write-Host ("  " + $_.Exception.Message) -ForegroundColor Red
    exit 1
}

$s = Get-PainelStatus
if (-not $s.Alcancavel) {
    Write-Host '  Configurado, mas o painel nao respondeu. Abra o painel e rode:' -ForegroundColor Yellow
    Write-Host '      .\Conectar-Painel.ps1 -EnviarTudo'
    Mostrar-Status
    return
}

$n = Sync-SupervisaoComPainel
Write-Host ("  Conectado. {0} registro(s) do historico enviados." -f $n) -ForegroundColor Green
Mostrar-Status
