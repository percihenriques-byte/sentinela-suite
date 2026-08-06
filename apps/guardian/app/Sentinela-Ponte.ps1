<#
    Sentinela-Ponte.ps1
    ------------------------------------------------------------------
    Ponte entre o app Windows e o painel local da suite (o servidor da
    CRM/VisiQuost em 127.0.0.1). O painel guarda o registro de supervisao
    num banco, cifrado, e mostra tudo numa tela so.

    Sem esta ponte, o que o app PowerShell classifica ficaria apenas no
    supervisao.jsonl e nunca apareceria no painel.

    - So fala com loopback. Recusa qualquer outro endereco.
    - Falha e SILENCIOSA de proposito: se o painel estiver desligado, a
      protecao nao pode parar por causa disso. O .jsonl continua sendo a
      verdade local e o Sync-SupervisaoComPainel envia depois.

    Requer Sentinela-Core.ps1 dot-sourceado (Get-SentinelaPaths, log).
    ------------------------------------------------------------------
#>

function Get-PainelArquivo {
    $p = Get-SentinelaPaths
    return (Join-Path $p.Base 'painel.json')
}

<#
  Configuracao da ponte: endereco do painel, token de ingestao, nome deste
  dispositivo e se o envio esta ligado.
#>
function Get-PainelConfig {
    $arq = Get-PainelArquivo
    $padrao = [pscustomobject]@{
        Url         = 'http://127.0.0.1:8000'
        Token       = ''
        Dispositivo = $env:COMPUTERNAME
        Ligado      = $false
    }
    if (-not (Test-Path $arq)) { return $padrao }
    try {
        $j = Get-Content $arq -Raw -Encoding UTF8 | ConvertFrom-Json
        return [pscustomobject]@{
            Url         = if ($j.Url) { $j.Url } else { $padrao.Url }
            Token       = if ($j.Token) { $j.Token } else { '' }
            Dispositivo = if ($j.Dispositivo) { $j.Dispositivo } else { $padrao.Dispositivo }
            Ligado      = [bool]$j.Ligado
        }
    } catch {
        return $padrao
    }
}

function Test-PainelLoopback {
    param([Parameter(Mandatory)][string]$Url)
    try {
        $h = ([uri]$Url).Host
        return ($h -eq '127.0.0.1' -or $h -eq 'localhost' -or $h -eq '::1')
    } catch { return $false }
}

<#
  Salva a configuracao da ponte. O token e credencial: fica so no
  ProgramData do Sentinela, que ja e a pasta protegida do app.
#>
function Set-PainelConfig {
    param(
        [string]$Url,
        [string]$Token,
        [string]$Dispositivo,
        [Nullable[bool]]$Ligado
    )
    Initialize-SentinelaStore | Out-Null
    $atual = Get-PainelConfig
    $novo = [pscustomobject]@{
        Url         = if ($PSBoundParameters.ContainsKey('Url'))         { $Url.Trim() }         else { $atual.Url }
        Token       = if ($PSBoundParameters.ContainsKey('Token'))       { $Token.Trim() }       else { $atual.Token }
        Dispositivo = if ($PSBoundParameters.ContainsKey('Dispositivo')) { $Dispositivo.Trim() } else { $atual.Dispositivo }
        Ligado      = if ($null -ne $Ligado)                             { [bool]$Ligado }       else { $atual.Ligado }
    }
    if (-not (Test-PainelLoopback -Url $novo.Url)) {
        throw "O painel so pode estar neste computador (127.0.0.1). Recebido: $($novo.Url)"
    }
    $novo | ConvertTo-Json | Set-Content -Path (Get-PainelArquivo) -Encoding UTF8
    return $novo
}

<#
  Converte um registro do supervisao.jsonl para o corpo que a API espera.
#>
function ConvertTo-PainelEvento {
    param([Parameter(Mandatory)]$Registro, [string]$Dispositivo)
    $conf = 0.0
    if ($null -ne $Registro.confianca) { $conf = [double]$Registro.confianca }
    if ($conf -lt 0) { $conf = 0.0 }
    if ($conf -gt 1) { $conf = 1.0 }
    return @{
        busca       = [string]$Registro.busca
        origem      = if ($Registro.origem) { [string]$Registro.origem } else { 'app' }
        dispositivo = if ($Dispositivo) { $Dispositivo } else { $env:COMPUTERNAME }
        tema        = if ($Registro.tema) { [string]$Registro.tema } else { $null }
        confianca   = $conf
        bloqueado   = [bool]$Registro.bloqueado
        ocorrido_em = if ($Registro.hora) { [string]$Registro.hora } else { $null }
    }
}

<#
  Envia registros ao painel. Devolve quantos foram aceitos (0 se a ponte
  estiver desligada ou o painel fora do ar).
  -Silencioso engole o erro; sem ele, o erro e escrito no log do Sentinela.
#>
function Send-PainelEventos {
    param(
        [Parameter(Mandatory)][array]$Registros,
        [switch]$Silencioso
    )
    if (-not $Registros -or $Registros.Count -eq 0) { return 0 }
    $cfg = Get-PainelConfig
    if (-not $cfg.Ligado -or -not $cfg.Token) { return 0 }
    if (-not (Test-PainelLoopback -Url $cfg.Url)) { return 0 }

    $enviados = 0
    # A API aceita ate 200 por requisicao.
    for ($i = 0; $i -lt $Registros.Count; $i += 200) {
        $fim = [Math]::Min($i + 199, $Registros.Count - 1)
        $lote = @()
        foreach ($r in $Registros[$i..$fim]) {
            if (-not $r.busca) { continue }
            $lote += (ConvertTo-PainelEvento -Registro $r -Dispositivo $cfg.Dispositivo)
        }
        if ($lote.Count -eq 0) { continue }
        $corpo = @{ eventos = $lote } | ConvertTo-Json -Depth 5 -Compress
        try {
            Invoke-RestMethod -Method Post -TimeoutSec 5 `
                -Uri ($cfg.Url.TrimEnd('/') + '/api/v1/sentinela/eventos') `
                -ContentType 'application/json; charset=utf-8' `
                -Headers @{ 'X-Sentinela-Token' = $cfg.Token } `
                -Body ([Text.Encoding]::UTF8.GetBytes($corpo)) | Out-Null
            $enviados += $lote.Count
        } catch {
            if (-not $Silencioso) {
                Write-SentinelaLog ("PAINEL: falha ao enviar " + $lote.Count + " evento(s) - " + $_.Exception.Message) 'WARN'
            }
            return $enviados
        }
    }
    return $enviados
}

<#
  Envia o supervisao.jsonl inteiro ao painel (util na primeira conexao ou
  depois de um periodo com o painel desligado).
#>
function Sync-SupervisaoComPainel {
    param([int]$Ultimos = 0)
    $registros = @(Get-SupervisaoRegistros -Ultimos $Ultimos)
    if ($registros.Count -eq 0) { return 0 }
    # Get-SupervisaoRegistros devolve do mais novo para o mais velho; o painel
    # fica mais coerente recebendo em ordem cronologica.
    [array]::Reverse($registros)
    $n = Send-PainelEventos -Registros $registros
    Write-SentinelaLog "PAINEL: $n de $($registros.Count) registro(s) enviados ao painel" 'INFO'
    return $n
}

<#
  Estado da ponte, para o painel do responsavel (GUI) e para o Status.
#>
function Get-PainelStatus {
    $cfg = Get-PainelConfig
    $alcancavel = $false
    if ($cfg.Ligado -and (Test-PainelLoopback -Url $cfg.Url)) {
        try {
            Invoke-RestMethod -Method Get -TimeoutSec 3 -Uri ($cfg.Url.TrimEnd('/') + '/healthz') | Out-Null
            $alcancavel = $true
        } catch { $alcancavel = $false }
    }
    [pscustomobject]@{
        Url         = $cfg.Url
        Dispositivo = $cfg.Dispositivo
        Ligado      = $cfg.Ligado
        TemToken    = [bool]$cfg.Token
        Alcancavel  = $alcancavel
    }
}
