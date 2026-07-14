<#
    Sentinela-Supervisao.ps1
    ------------------------------------------------------------------
    Registro de supervisao (fiscalizacao). Guarda o que foi buscado e
    como a IA classificou, para o responsavel acompanhar. Tudo fica
    LOCAL, na maquina (privacidade: nada vai para a internet).

    Formato: uma linha JSON por evento em  <base>\supervisao.jsonl

    Requer Sentinela-Core.ps1 (Get-SentinelaPaths) e
    Sentinela-Classificador.ps1 (Get-ClassificacaoConteudo) dot-sourceados.
    ------------------------------------------------------------------
#>

function Get-SupervisaoArquivo {
    $p = Get-SentinelaPaths
    return (Join-Path $p.Base 'supervisao.jsonl')
}

<#
  Registra uma busca. Se -Resultado nao for passado, classifica na hora.
  Retorna o objeto de classificacao.
#>
function Add-SupervisaoRegistro {
    param(
        [Parameter(Mandatory)][string]$Texto,
        [string]$Origem = 'desconhecida',
        $Resultado
    )
    Initialize-SentinelaStore | Out-Null
    if ($null -eq $Resultado) { $Resultado = Get-ClassificacaoConteudo -Texto $Texto }

    $registro = [pscustomobject]@{
        hora      = (Get-Date).ToString('o')
        busca     = $Texto
        origem    = $Origem
        tema      = $Resultado.Categoria
        confianca = $Resultado.Confianca
        bloqueado = [bool]$Resultado.Bloquear
    }
    $linha = ($registro | ConvertTo-Json -Compress)
    $arq = Get-SupervisaoArquivo
    Add-Content -Path $arq -Value $linha -Encoding UTF8
    # cap: mantem apenas as ultimas 2000 linhas (evita crescimento sem limite) - BUG-12
    $todas = @(Get-Content $arq -Encoding UTF8)
    if ($todas.Count -gt 2000) {
        $todas[($todas.Count - 2000)..($todas.Count - 1)] | Set-Content -Path $arq -Encoding UTF8
    }

    if ($Resultado.Bloquear) {
        Write-SentinelaLog ("SUPERVISAO: busca bloqueada [{0}] '{1}' (origem {2})" -f $Resultado.Categoria, $Texto, $Origem) 'WARN'
    }
    return $Resultado
}

<#
  Le os registros de supervisao (mais recentes primeiro).
  -SomenteBloqueados mostra so o que foi barrado.
#>
function Get-SupervisaoRegistros {
    param([int]$Ultimos = 100, [switch]$SomenteBloqueados)
    $arq = Get-SupervisaoArquivo
    if (-not (Test-Path $arq)) { return @() }
    $itens = @()
    foreach ($l in (Get-Content $arq -Encoding UTF8)) {
        if ([string]::IsNullOrWhiteSpace($l)) { continue }
        try { $itens += ($l | ConvertFrom-Json) } catch { }
    }
    if ($SomenteBloqueados) { $itens = $itens | Where-Object { $_.bloqueado } }
    $itens = @($itens)
    [array]::Reverse($itens)
    if ($Ultimos -gt 0 -and $itens.Count -gt $Ultimos) { $itens = $itens[0..($Ultimos-1)] }
    return $itens
}

<#
  Importa um arquivo .jsonl exportado pela extensao do navegador
  (botao "Exportar" no popup) para o registro de supervisao do app.
  Assim o painel do responsavel mostra o que a extensao capturou.
#>
function Import-SupervisaoDeArquivo {
    param([Parameter(Mandatory)][string]$Arquivo)
    if (-not (Test-Path $Arquivo)) { throw "Arquivo nao encontrado: $Arquivo" }
    Initialize-SentinelaStore | Out-Null
    $destino = Get-SupervisaoArquivo
    $n = 0
    foreach ($l in (Get-Content $Arquivo -Encoding UTF8)) {
        if ([string]::IsNullOrWhiteSpace($l)) { continue }
        try { $obj = $l | ConvertFrom-Json } catch { continue }
        Add-Content -Path $destino -Value ($obj | ConvertTo-Json -Compress) -Encoding UTF8
        $n++
    }
    Write-SentinelaLog "SUPERVISAO: importados $n registros de $Arquivo" 'INFO'
    return $n
}

<#
  Resumo para o responsavel: total, bloqueadas, e contagem por tema.
#>
function Get-SupervisaoResumo {
    $todos = Get-SupervisaoRegistros -Ultimos 0
    $bloq = @($todos | Where-Object { $_.bloqueado })
    $porTema = $bloq | Group-Object tema | ForEach-Object {
        [pscustomobject]@{ Tema=$_.Name; Vezes=$_.Count }
    } | Sort-Object Vezes -Descending
    [pscustomobject]@{
        Total          = @($todos).Count
        Bloqueadas     = $bloq.Count
        TemasPrincipais= $porTema
    }
}
