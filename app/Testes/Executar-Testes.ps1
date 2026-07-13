<#
    Executar-Testes.ps1
    ------------------------------------------------------------------
    Testes automatizados do Sentinela, TODOS em modo simulacao (nada
    real e alterado). Verificam o comportamento central:
      - ativar aplica DNS + hosts
      - desativar remove o bloco hosts
      - o guardiao reaplica se adulterado
      - PIN: hash correto, verificacao certa/errada, validacao
      - PIN nunca aparece em texto no config.json

    Uso:  .\Executar-Testes.ps1
    Saida: relatorio com contagem; codigo de saida 0 (ok) ou 1 (falhou).
    ------------------------------------------------------------------
#>
$ErrorActionPreference = 'Stop'
$env:SENTINELA_SIMULAR = '1'

$appDir = Split-Path $PSScriptRoot -Parent
. (Join-Path $appDir 'Sentinela-Core.ps1')
. (Join-Path $appDir 'Sentinela-Pin.ps1')

$script:pass = 0
$script:fail = 0

function Assert {
    param([string]$Nome, [bool]$Condicao)
    if ($Condicao) {
        $script:pass++
        Write-Host ('  [OK]   ' + $Nome) -ForegroundColor Green
    } else {
        $script:fail++
        Write-Host ('  [FALHA] ' + $Nome) -ForegroundColor Red
    }
}

function Reset-Sandbox {
    $p = Get-SentinelaPaths
    if (Test-Path $p.Base) { Remove-Item $p.Base -Recurse -Force -ErrorAction SilentlyContinue }
    Initialize-SentinelaStore | Out-Null
}

Write-Host ''
Write-Host '  === TESTES DO SENTINELA (modo simulacao) ===' -ForegroundColor Cyan
Write-Host ''

# --- Grupo 1: ativar/desativar --------------------------------------
Write-Host '  Grupo 1: ativar e desativar'
Reset-Sandbox
Enable-Sentinela -Simular
Assert 'Apos ativar, o estado e ATIVO'            ((Get-SentinelaState).ativo -eq $true)
Assert 'Apos ativar, o bloco hosts esta aplicado' (Test-SentinelaHostsApplied)
$hostsTxt = Get-Content (Get-SentinelaPaths).HostsFile -Raw
Assert 'hosts contem www.google.com forcado'      ($hostsTxt -match 'www\.google\.com')
Assert 'hosts contem restrict do youtube (IP)'    ($hostsTxt -match '216\.239\.38\.120')

Disable-Sentinela -Simular
Assert 'Apos desativar, o estado e DESLIGADO'      ((Get-SentinelaState).ativo -eq $false)
Assert 'Apos desativar, o bloco hosts sumiu'       (-not (Test-SentinelaHostsApplied))
$hostsTxt2 = Get-Content (Get-SentinelaPaths).HostsFile -Raw
Assert 'hosts original preservado (localhost)'     ($hostsTxt2 -match '127\.0\.0\.1')

# --- Grupo 2: guardiao ----------------------------------------------
Write-Host ''
Write-Host '  Grupo 2: guardiao anti-adulteracao'
Reset-Sandbox
Enable-Sentinela -Simular
Clear-SentinelaHosts   # simula a crianca removendo o bloco
Assert 'Adulteracao removeu o bloco hosts'         (-not (Test-SentinelaHostsApplied))
& (Join-Path $appDir 'Sentinela-Guardiao.ps1') -Simular | Out-Null
Assert 'Guardiao reaplicou o bloco hosts'          (Test-SentinelaHostsApplied)

# guardiao NAO deve reaplicar se estiver oficialmente desligado
Disable-Sentinela -Simular
Clear-SentinelaHosts
& (Join-Path $appDir 'Sentinela-Guardiao.ps1') -Simular | Out-Null
Assert 'Guardiao respeita desligamento oficial'    (-not (Test-SentinelaHostsApplied))

# --- Grupo 3: PIN ---------------------------------------------------
Write-Host ''
Write-Host '  Grupo 3: trava por PIN'
Reset-Sandbox
Set-SentinelaPin -Pin '2026'
Assert 'PIN fica configurado'                      (Test-SentinelaPinConfigured)
Assert 'PIN correto e aceito'                      (Test-SentinelaPin -Pin '2026')
Assert 'PIN errado e rejeitado'                    (-not (Test-SentinelaPin -Pin '0000'))

$cfg = Get-SentinelaConfig
Assert 'PIN guardado como hash SHA-256 (64 hex)'   (($cfg.pinHash.Length -eq 64) -and ($cfg.pinHash -match '^[0-9a-f]+$'))
Assert 'hash confere com SHA-256(salt:PIN)'        ($cfg.pinHash -eq (Get-SentinelaPinHash -Pin '2026' -Salt $cfg.pinSalt))
$campoComPinCru = @($cfg.PSObject.Properties | Where-Object { $_.Name -notin @('pinHash','pinSalt','criadoEm') -and "$($_.Value)" -eq '2026' })
Assert 'nenhum campo guarda o PIN em texto puro'   ($campoComPinCru.Count -eq 0)

$rejeitou = $false
try { Set-SentinelaPin -Pin '12' } catch { $rejeitou = $true }
Assert 'PIN curto (<4) e rejeitado'                $rejeitou

$rejeitou2 = $false
try { Set-SentinelaPin -Pin 'abcd' } catch { $rejeitou2 = $true }
Assert 'PIN nao-numerico e rejeitado'              $rejeitou2

# troca de PIN muda o hash
Set-SentinelaPin -Pin '2026'
$h1 = (Get-SentinelaConfig).pinHash
Set-SentinelaPin -Pin '9999'
$h2 = (Get-SentinelaConfig).pinHash
Assert 'Trocar o PIN muda o hash guardado'         ($h1 -ne $h2)
Assert 'Novo PIN passa a valer'                    (Test-SentinelaPin -Pin '9999')

# --- Grupo 4: idempotencia ------------------------------------------
Write-Host ''
Write-Host '  Grupo 4: idempotencia (ativar duas vezes nao duplica)'
Reset-Sandbox
Enable-Sentinela -Simular
Enable-Sentinela -Simular
$txt = Get-Content (Get-SentinelaPaths).HostsFile -Raw
$ocorrencias = ([regex]::Matches($txt, [regex]::Escape('>>> SENTINELA'))).Count
Assert 'Bloco hosts aparece apenas 1 vez'          ($ocorrencias -eq 1)

# --- Relatorio ------------------------------------------------------
Write-Host ''
Write-Host '  ------------------------------------------' -ForegroundColor DarkGray
Write-Host ("  RESULTADO: {0} passaram, {1} falharam" -f $script:pass, $script:fail) -ForegroundColor $(if ($script:fail -eq 0) { 'Green' } else { 'Red' })
Write-Host ''

# limpa a sandbox ao final
$p = Get-SentinelaPaths
if (Test-Path $p.Base) { Remove-Item $p.Base -Recurse -Force -ErrorAction SilentlyContinue }

if ($script:fail -gt 0) { exit 1 } else { exit 0 }
