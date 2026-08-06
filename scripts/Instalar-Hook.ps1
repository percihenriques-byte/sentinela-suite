<#
    Instalar-Hook.ps1
    ------------------------------------------------------------------
    Instala um hook de pre-push que roda o portao rapido
    (Verificar-Tudo.ps1 -Rapido, ~7s) antes de deixar voce empurrar.

    Por que existe: o CI so pega a regressao DEPOIS que ela ja esta no
    repositorio. O hook pega antes. E o gasto e de segundos, porque o portao
    rapido roda as duas verificacoes que mais protegem — paridade dos
    classificadores e os achados de auditoria — e deixa a suite completa para
    o Verificar-Tudo.ps1 sem argumento.

    Hooks nao sao versionados pelo git; por isso este instalador existe.

    Uso:
        .\scripts\Instalar-Hook.ps1
        .\scripts\Instalar-Hook.ps1 -Remover

    Para empurrar pulando o hook (use com consciencia):
        git push --no-verify
    ------------------------------------------------------------------
#>
param([switch]$Remover)

$raiz = Split-Path $PSScriptRoot -Parent
$hooks = Join-Path $raiz '.git\hooks'
$alvo = Join-Path $hooks 'pre-push'

if (-not (Test-Path $hooks)) {
    Write-Host '  Nao achei .git\hooks - este script roda dentro do repositorio.' -ForegroundColor Red
    exit 1
}

if ($Remover) {
    if (Test-Path $alvo) {
        Remove-Item $alvo -Force
        Write-Host '  Hook de pre-push removido.' -ForegroundColor Yellow
    } else {
        Write-Host '  Nao havia hook instalado.' -ForegroundColor DarkGray
    }
    exit 0
}

# Git no Windows executa hooks com sh, entao o hook e shell chamando o PowerShell.
$conteudo = @'
#!/bin/sh
# Instalado por scripts/Instalar-Hook.ps1 - portao rapido antes do push.
# Para pular conscientemente: git push --no-verify
raiz="$(git rev-parse --show-toplevel)"
echo ""
echo "  pre-push: rodando o portao rapido da suite..."
powershell -NoProfile -ExecutionPolicy Bypass -File "$raiz/Verificar-Tudo.ps1" -Rapido
codigo=$?
if [ $codigo -ne 0 ]; then
  echo ""
  echo "  push CANCELADO: o portao falhou. Conserte, ou use --no-verify se souber o que esta fazendo."
  echo ""
fi
exit $codigo
'@

Set-Content -Path $alvo -Value $conteudo -Encoding ASCII -NoNewline
Write-Host ''
Write-Host '  Hook de pre-push instalado.' -ForegroundColor Green
Write-Host ("  {0}" -f $alvo) -ForegroundColor DarkGray
Write-Host '  A partir de agora, todo push roda o portao rapido (~7s) antes.' -ForegroundColor DarkGray
Write-Host ''
