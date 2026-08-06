<#
    Ver-Supervisao.ps1
    Mostra ao responsavel o que foi buscado (registro de supervisao).
    Uso:
        .\Ver-Supervisao.ps1                       # resumo + ultimas buscas
        .\Ver-Supervisao.ps1 -SomenteBloqueadas    # so o que foi barrado
        .\Ver-Supervisao.ps1 -Importar arquivo.jsonl  # importa export da extensao
#>
param([switch]$SomenteBloqueadas, [string]$Importar, [switch]$Simular)

. (Join-Path $PSScriptRoot 'Sentinela-Core.ps1')
. (Join-Path $PSScriptRoot 'Sentinela-Pin.ps1')
. (Join-Path $PSScriptRoot 'Sentinela-Classificador.ps1')
. (Join-Path $PSScriptRoot 'Sentinela-Supervisao.ps1')

if ($Simular) { $env:SENTINELA_SIMULAR = '1' }

if ($Importar) {
    $n = Import-SupervisaoDeArquivo -Arquivo $Importar
    Write-Host ("  Importados $n registros da extensao.") -ForegroundColor Green
}

$res = Get-SupervisaoResumo
Write-Host ''
Write-Host '  === SUPERVISAO DO SENTINELA ===' -ForegroundColor Cyan
Write-Host ("  Total de buscas : " + $res.Total)
Write-Host ("  Bloqueadas......: " + $res.Bloqueadas) -ForegroundColor $(if ($res.Bloqueadas -gt 0) { 'Red' } else { 'Green' })
if ($res.TemasPrincipais) {
    Write-Host '  Temas mais barrados:'
    $res.TemasPrincipais | ForEach-Object { Write-Host ("    - {0}: {1}x" -f $_.Tema, $_.Vezes) }
}
Write-Host ''
Write-Host '  Ultimas buscas:' -ForegroundColor Cyan
$itens = Get-SupervisaoRegistros -Ultimos 30 -SomenteBloqueados:$SomenteBloqueadas
if (-not $itens -or @($itens).Count -eq 0) {
    Write-Host '    (nenhum registro ainda)' -ForegroundColor DarkGray
} else {
    foreach ($i in $itens) {
        $hora = try { ([datetime]$i.hora).ToString('dd/MM HH:mm') } catch { $i.hora }
        if ($i.bloqueado) {
            Write-Host ("    [{0}] BLOQUEADA {1,-18} {2}" -f $hora, $i.tema, $i.busca) -ForegroundColor Red
        } else {
            Write-Host ("    [{0}] liberada  {1,-18} {2}" -f $hora, '', $i.busca) -ForegroundColor DarkGray
        }
    }
}
Write-Host ''
