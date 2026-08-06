<#
    Classificar-Busca.ps1
    Ferramenta para o responsavel testar a IA local do Sentinela.
    Digite uma busca e veja como o classificador reage (categoria,
    confianca e o porque). Nao altera nada no sistema.

    Uso:
        .\Classificar-Busca.ps1                 # modo interativo
        .\Classificar-Busca.ps1 -Texto 's3x0'   # uma busca so
#>
param([string]$Texto)

. (Join-Path $PSScriptRoot 'Sentinela-Classificador.ps1')

function Mostrar {
    param([string]$q)
    $r = Get-ClassificacaoConteudo -Texto $q
    Write-Host ''
    if ($r.Bloquear) {
        Write-Host ('  [ BLOQUEAR ]  ' + $q) -ForegroundColor Red
        Write-Host ('  Categoria : ' + $r.Categoria)
        Write-Host ('  Confianca : ' + [int]($r.Confianca * 100) + '%')
        Write-Host ('  Sinais    : ' + ($r.Sinais -join ', ')) -ForegroundColor DarkGray
    } else {
        Write-Host ('  [ LIBERAR  ]  ' + $q) -ForegroundColor Green
        Write-Host ('  ' + $r.Motivo) -ForegroundColor DarkGray
    }
}

if ($Texto) { Mostrar $Texto; return }

Write-Host ''
Write-Host '  IA local do Sentinela - teste de classificacao' -ForegroundColor Cyan
Write-Host '  (digite uma busca; ENTER vazio para sair)' -ForegroundColor DarkGray
while ($true) {
    $q = Read-Host '  busca'
    if ([string]::IsNullOrWhiteSpace($q)) { break }
    Mostrar $q
}
