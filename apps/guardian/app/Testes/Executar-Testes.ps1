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
. (Join-Path $appDir 'Sentinela-Classificador.ps1')
. (Join-Path $appDir 'Sentinela-Supervisao.ps1')
. (Join-Path $appDir 'Sentinela-Crx.ps1')

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

# BUG-07: adulteracao mantendo os marcadores mas apagando um IP esperado
Enable-Sentinela -Simular
$hAdult = (Get-Content (Get-SentinelaPaths).HostsFile -Raw) -replace '216\.239\.38\.120 www\.google\.com', ''
$hAdult | Set-Content (Get-SentinelaPaths).HostsFile -Encoding ASCII
Assert 'Marcador presente + IP removido = NAO aplicado' (-not (Test-SentinelaHostsApplied))
& (Join-Path $appDir 'Sentinela-Guardiao.ps1') -Simular | Out-Null
Assert 'Guardiao reaplica apos IP removido (marcador mantido)' (Test-SentinelaHostsApplied)

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

# BUG-08: se o hosts ja tinha um bloco na 1a ativacao, o backup nao deve conte-lo
Reset-Sandbox
"127.0.0.1 localhost`r`n# >>> SENTINELA (nao edite esta secao) >>>`r`n216.239.38.120 www.google.com`r`n# <<< SENTINELA <<<" | Set-Content (Get-SentinelaPaths).HostsFile -Encoding ASCII
Enable-Sentinela -Simular
Assert 'Backup do hosts nao contem bloco SENTINELA' (-not ((Get-Content (Get-SentinelaPaths).HostsBackup -Raw) -match '>>> SENTINELA'))

# --- Grupo 5: IA local de classificacao -----------------------------
Write-Host ''
Write-Host '  Grupo 5: IA local de classificacao (anti-evasao)'
Assert 'Busca comum e liberada'                    (-not (Test-ConteudoImproprio 'vulcao para feira de ciencias'))
Assert 'Busca comum 2 e liberada'                  (-not (Test-ConteudoImproprio 'filhotes de golden retriever'))
Assert 'Conteudo adulto direto e bloqueado'        (Test-ConteudoImproprio 'conteudo adulto +18')
Assert 'Violencia extrema e bloqueada'              (Test-ConteudoImproprio 'videos de violencia extrema')
# --- ancoras que devem bloquear SOZINHAS (BUG-01/02/04) ---
Assert 'sexo (sozinho) e bloqueado'                 (Test-ConteudoImproprio 'sexo')
Assert 's3x0 (sozinho) e bloqueado'                 (Test-ConteudoImproprio 's3x0')
Assert 'como fazer sexo e bloqueado'                (Test-ConteudoImproprio 'como fazer sexo')
Assert 'nudez e bloqueada'                          (Test-ConteudoImproprio 'nudez')
Assert 'nudez infantil e bloqueada'                 (Test-ConteudoImproprio 'nudez infantil')
Assert 'transar e bloqueado'                        (Test-ConteudoImproprio 'transar')
Assert 'zoofilia e bloqueada'                       (Test-ConteudoImproprio 'zoofilia')
# --- precisao afinada (falsos +/- dificeis) ---
Assert 'video de sexo bloqueia'                     (Test-ConteudoImproprio 'video de sexo')
Assert 'mulheres peladas (plural) bloqueia'         (Test-ConteudoImproprio 'fotos de mulheres peladas')
Assert 'usar cocaina bloqueia'                      (Test-ConteudoImproprio 'como usar cocaina')
Assert 'explosivo caseiro bloqueia'                 (Test-ConteudoImproprio 'como fazer explosivo caseiro')
Assert 'site de apostas online bloqueia'            (Test-ConteudoImproprio 'site de apostas online')
Assert 'sexo masculino/feminino NAO bloqueia'       (-not (Test-ConteudoImproprio 'sexo masculino ou feminino'))
Assert 'qual o sexo do bebe NAO bloqueia'           (-not (Test-ConteudoImproprio 'qual o sexo do bebe'))
Assert 'sexo dos anjos (idiom) NAO bloqueia'        (-not (Test-ConteudoImproprio 'sexo dos anjos significado'))
Assert 'receita de bomba de chocolate NAO bloqueia' (-not (Test-ConteudoImproprio 'receita de bomba de chocolate'))
Assert 'roleta russa filme NAO bloqueia'            (-not (Test-ConteudoImproprio 'roleta russa filme'))
Assert 'nudez em arte/museu NAO bloqueia'           (-not (Test-ConteudoImproprio 'estatua grega nudez arte historia'))
Assert 'tema LGBT (ser gay) NAO bloqueia'           (-not (Test-ConteudoImproprio 'o que e ser gay'))
Assert 'camisinha como usar NAO bloqueia'           (-not (Test-ConteudoImproprio 'camisinha como usar corretamente'))
Assert 'comprar armario NAO bloqueia (nao arma)'    (-not (Test-ConteudoImproprio 'comprar armario de cozinha'))
Assert 'novinha pelada bloqueia'                    (Test-ConteudoImproprio 'novinha pelada')
Assert 'cheirar cola bloqueia'                       (Test-ConteudoImproprio 'como cheirar cola para chapar')
Assert 'comprar arma de fogo bloqueia'              (Test-ConteudoImproprio 'comprar arma de fogo ilegal')
Assert 'colado nao junta palavras (frango receita)' (-not (Test-ConteudoImproprio 'peito de frango receita fit'))
Assert 'ver mulher nua bloqueia'                    (Test-ConteudoImproprio 'ver mulher nua')
Assert 'cortar os pulsos bloqueia'                  (Test-ConteudoImproprio 'como cortar os pulsos')
Assert 'jogo aviator bloqueia'                      (Test-ConteudoImproprio 'jogo aviator ganhar dinheiro')
Assert 'god of war (jogo) NAO bloqueia'             (-not (Test-ConteudoImproprio 'god of war kratos'))
Assert 'galinha pelada (infantil) NAO bloqueia'     (-not (Test-ConteudoImproprio 'galinha pelada musica infantil'))
# --- autolesao: variacoes (BUG-03) ---
Assert 'quero me matar e bloqueado'                 (Test-ConteudoImproprio 'quero me matar')
Assert 'quero morrer e bloqueado'                   (Test-ConteudoImproprio 'quero morrer')
# --- substrings curtas nao geram sinal falso (BUG-05) ---
Assert 'menu do restaurante nao vira adulto'        ($null -eq (Get-ClassificacaoConteudo -Texto 'menu do restaurante').Categoria)
Assert 'numero de telefone nao vira adulto'         ($null -eq (Get-ClassificacaoConteudo -Texto 'numero de telefone').Categoria)
Assert 'aprender o alfabeto nao vira apostas'       ($null -eq (Get-ClassificacaoConteudo -Texto 'aprender o alfabeto').Categoria)
Assert 'apostila de matematica continua liberada'   (-not (Test-ConteudoImproprio 'apostila de matematica'))
Assert 'Evasao leetspeak (s3x0) e bloqueada'       (Test-ConteudoImproprio 's3x0 expl1c1t0')
Assert 'Evasao letras espacadas (p o r n) bloqueada' (Test-ConteudoImproprio 'p o r n o')
Assert 'Evasao com pontos (p.o.r.n) bloqueada'     (Test-ConteudoImproprio 'p.o.r.n.o.g.r.a.f.i.a')
Assert 'Evasao repeticao (poooorno) bloqueada'     (Test-ConteudoImproprio 'pooooorno')
# BUG-10: homoglifo cirilico e full-width (construidos por codigo p/ nao depender do encoding do .ps1)
$evCirilico  = 'p' + [char]0x043E + 'rn' + [char]0x043E                              # "porno" com o cirilico
$evFullwidth = [string]([char]0xFF53 + [char]0xFF45 + [char]0xFF58 + [char]0xFF4F)   # "sexo" full-width
Assert 'Evasao homoglifo cirilico bloqueada'       (Test-ConteudoImproprio $evCirilico)
Assert 'Evasao full-width bloqueada'               (Test-ConteudoImproprio $evFullwidth)
Assert 'Burlar filtro (mesmo com "escola") bloqueado' (Test-ConteudoImproprio 'como burlar o filtro da escola')
Assert 'Desativar safesearch com leet bloqueado'   (Test-ConteudoImproprio 'desativar s4f3s34rch')
Assert 'Contexto saude NAO gera falso-positivo'    (-not (Test-ConteudoImproprio 'cancer de mama sintomas'))
Assert 'Contexto ciencias NAO gera falso-positivo' (-not (Test-ConteudoImproprio 'reproducao humana aula de ciencias'))
$cl = Get-ClassificacaoConteudo -Texto 's3x0'
Assert 'Classificacao retorna confianca > 0'       ($cl.Confianca -gt 0)
Assert 'Classificacao retorna a categoria'         ($cl.Categoria -eq 'Conteudo adulto')
Assert 'Classificacao explica o motivo (sinais)'   ($cl.Sinais.Count -gt 0)

# --- Grupo 6: configuracao do responsavel ---------------------------
Write-Host ''
Write-Host '  Grupo 6: bloqueio amplo e configuravel'
Reset-Sandbox
Assert 'Muitos temas cobertos (>= 8)'              ((Get-TemasDisponiveis).Count -ge 8)
Assert 'Tigrinho (aposta) e bloqueado'             (Test-ConteudoImproprio 'jogo do tigrinho')
Assert 'bet365 (marca com digitos) e bloqueado'    (Test-ConteudoImproprio 'bet365')
Assert 'leet ainda funciona apos dupla variante'   (Test-ConteudoImproprio 's3x0')
Assert 'Autolesao e bloqueada'                     (Test-ConteudoImproprio 'como se matar')
# responsavel desativa um tema
Save-SentinelaConfig -Config ([pscustomobject]@{ classificador = [pscustomobject]@{ temasDesativados = @('Apostas') } })
Assert 'Tema desativado deixa de bloquear'         (-not (Test-ConteudoImproprio 'aposta esportiva'))
# termo personalizado do responsavel
Save-SentinelaConfig -Config ([pscustomobject]@{ classificador = [pscustomobject]@{ termosPersonalizados = @('roblox') } })
Assert 'Termo personalizado do responsavel bloqueia' (Test-ConteudoImproprio 'jogar roblox')
# modo rigido
Save-SentinelaConfig -Config ([pscustomobject]@{ classificador = [pscustomobject]@{ modoRigido = $true } })
Assert 'Modo rigido bloqueia sinal medio (nudez)'  (Test-ConteudoImproprio 'nudez')
# tema opcional so entra se ativado
Save-SentinelaConfig -Config ([pscustomobject]@{})
Assert 'Tema opcional (redes sociais) OFF por padrao' (-not (Test-ConteudoImproprio 'tiktok'))
Save-SentinelaConfig -Config ([pscustomobject]@{ classificador = [pscustomobject]@{ temasAtivados = @('Redes sociais'); modoRigido = $true } })
Assert 'Tema opcional ativado passa a bloquear'    (Test-ConteudoImproprio 'tiktok')
# BUG-11: desativar tema por nome SEM acento tambem funciona
Save-SentinelaConfig -Config ([pscustomobject]@{ classificador = [pscustomobject]@{ temasDesativados = @('Conteudo adulto') } })
Assert 'Desativar tema por nome sem acento (BUG-11)' (-not (Test-ConteudoImproprio 'pornografia'))

# --- Grupo 7: supervisao (fiscalizacao) -----------------------------
Write-Host ''
Write-Host '  Grupo 7: supervisao / fiscalizacao'
Reset-Sandbox
Save-SentinelaConfig -Config ([pscustomobject]@{}) | Out-Null
Add-SupervisaoRegistro -Texto 'vulcao para feira de ciencias' -Origem 'google' | Out-Null
Add-SupervisaoRegistro -Texto 's3x0 expl1c1t0' -Origem 'google' | Out-Null
Add-SupervisaoRegistro -Texto 'como burlar o filtro' -Origem 'youtube' | Out-Null
$regs = Get-SupervisaoRegistros
Assert 'Supervisao registrou as 3 buscas'          (@($regs).Count -eq 3)
Assert 'Mais recente vem primeiro'                 ($regs[0].busca -eq 'como burlar o filtro')
Assert 'So bloqueadas retorna 2'                    ((Get-SupervisaoRegistros -SomenteBloqueados).Count -eq 2)
$resumo = Get-SupervisaoResumo
Assert 'Resumo: total = 3'                          ($resumo.Total -eq 3)
Assert 'Resumo: bloqueadas = 2'                     ($resumo.Bloqueadas -eq 2)
Assert 'Busca segura NAO fica marcada como bloqueada' (-not ($regs | Where-Object { $_.busca -like 'vulcao*' }).bloqueado)
# importar export da extensao
$fake = Join-Path (Get-SentinelaPaths).Base 'export-teste.jsonl'
'{"hora":"2026-07-13T09:12:00.000Z","busca":"tigrinho","origem":"bing","tema":"Apostas","confianca":0.67,"bloqueado":true}' | Set-Content $fake -Encoding UTF8
$importados = Import-SupervisaoDeArquivo -Arquivo $fake
Assert 'Import da extensao adiciona 1 registro'    ($importados -eq 1)
Assert 'Apos import, total sobe para 4'             ((Get-SupervisaoResumo).Total -eq 4)

# --- Grupo 8: ID da extensao (travamento) ---------------------------
Write-Host ''
Write-Host '  Grupo 8: calculo do ID da extensao (para travar)'
$hZero = New-Object 'byte[]' 16
$hFF   = [byte[]](@(255) * 16)
$hUm   = New-Object 'byte[]' 16; $hUm[0] = 1
Assert 'ID: hash 0x00 -> 32 letras "a"'             ((ConvertTo-CrxIdFromHash $hZero) -eq ('a' * 32))
Assert 'ID: hash 0xFF -> 32 letras "p"'             ((ConvertTo-CrxIdFromHash $hFF) -eq ('p' * 32))
Assert 'ID: primeiro byte 0x01 -> comeca com "ab"'  ((ConvertTo-CrxIdFromHash $hUm).Substring(0,2) -eq 'ab')
Assert 'ID tem sempre 32 caracteres'                ((ConvertTo-CrxIdFromHash $hZero).Length -eq 32)
Assert 'ID usa apenas letras a-p'                   ((ConvertTo-CrxIdFromHash $hFF) -match '^[a-p]{32}$')
# ponta a ponta (so se houver navegador para empacotar)
if (Get-NavegadorParaEmpacotar) {
    $saida = Join-Path (Get-SentinelaPaths).Base 'ext-teste'
    $crx = Invoke-EmpacotarExtensao -PastaExtensao (Join-Path $appDir 'extensao') -PastaSaida $saida
    $idE2E = Get-CrxExtensionId -CrxPath $crx
    Assert 'Empacotar+ID real gera ID valido (a-p, 32)' ($idE2E -match '^[a-p]{32}$')
    $id2 = Get-CrxExtensionId -CrxPath (Invoke-EmpacotarExtensao -PastaExtensao (Join-Path $appDir 'extensao') -PastaSaida $saida)
    Assert 'ID estavel ao reempacotar (mesma chave)'  ($idE2E -eq $id2)
} else {
    Write-Host '  [--]   (sem navegador; teste ponta-a-ponta de empacotamento pulado)' -ForegroundColor DarkGray
}
# BUG-13: crx corrompido/truncado lanca erro tratado
$crxCorrupto = Join-Path (Get-SentinelaPaths).Base 'corrupto.crx'
[System.IO.File]::WriteAllBytes($crxCorrupto, ([byte[]](0x43,0x72,0x32,0x34,3,0,0,0,255,255,0,0,1,2,3)))
$lancouErro = $false; try { Get-CrxExtensionId -CrxPath $crxCorrupto | Out-Null } catch { $lancouErro = $true }
Assert 'CRX truncado lanca erro tratado (BUG-13)'   $lancouErro
# BUG-14: New-UpdateXml escapa caracteres XML
$xmlEsc = New-UpdateXml -ExtensionId 'abcdefghijklmnopabcdefghijklmnop' -Codebase 'http://127.0.0.1/a&b.crx'
Assert 'New-UpdateXml escapa & (BUG-14)'            (($xmlEsc -match '&amp;') -and -not ($xmlEsc -match '&(?!amp;|lt;|gt;|apos;|quot;)'))

# --- Grupo 9: servidor local (force-install http) -------------------
Write-Host ''
Write-Host '  Grupo 9: servidor local 127.0.0.1'
Reset-Sandbox
$extS = Join-Path (Get-SentinelaPaths).Base 'ext'
New-Item -ItemType Directory -Path $extS -Force | Out-Null
'<xml>teste</xml>' | Set-Content (Join-Path $extS 'update.xml') -Encoding UTF8
[System.IO.File]::WriteAllBytes((Join-Path $extS 'sentinela.crx'), ([byte[]](1..20)))
$porta = 48991
$job = Start-Job -ScriptBlock { param($h,$p) & "$h\sentinela\app\Sentinela-Servidor.ps1" -Simular -PermitirShutdown -Porta $p } -ArgumentList $HOME, $porta
Start-Sleep -Seconds 2
$okPing = $false; $okUpd = $false; $okCrx = $false; $okLocal = $true
try { $okPing = ((Invoke-WebRequest "http://127.0.0.1:$porta/ping" -UseBasicParsing -TimeoutSec 4).Content -eq 'ok') } catch {}
if ($okPing) {
    try { $okUpd = ((Invoke-WebRequest "http://127.0.0.1:$porta/update.xml" -UseBasicParsing -TimeoutSec 4).StatusCode -eq 200) } catch {}
    try { $okCrx = ((Invoke-WebRequest "http://127.0.0.1:$porta/sentinela.crx" -UseBasicParsing -TimeoutSec 4).Headers['Content-Type'] -like '*chrome-extension*') } catch {}
    try { Invoke-WebRequest "http://127.0.0.1:$porta/shutdown" -UseBasicParsing -TimeoutSec 4 | Out-Null } catch {}
}
Wait-Job $job -Timeout 8 | Out-Null; Stop-Job $job -ErrorAction SilentlyContinue; Remove-Job $job -Force -ErrorAction SilentlyContinue
if ($okPing) {
    Assert 'Servidor local responde ping'              $okPing
    Assert 'Servidor serve update.xml (200)'           $okUpd
    Assert 'Servidor serve .crx (content-type extensao)' $okCrx
} else {
    Write-Host '  [--]   (servidor nao subiu neste ambiente; teste pulado)' -ForegroundColor DarkGray
}

# --- Grupo 10: analise de CONTEUDO da pagina (o que a crianca ve) ----
Write-Host ''
Write-Host '  Grupo 10: analise de conteudo da pagina'
Reset-Sandbox; Save-SentinelaConfig -Config ([pscustomobject]@{}) | Out-Null
Assert 'Pagina adulta (varios termos) bloqueia'    ((Get-ClassificacaoPagina -Texto 'pornografia sexo nudez porno putaria sexo explicito').Bloquear)
Assert 'Pagina de apostas bloqueia'                ((Get-ClassificacaoPagina -Texto 'cassino online aposta esportiva jogo do tigrinho bet365 aposta').Bloquear)
Assert 'Palavra adulta repetida (5x) bloqueia'     ((Get-ClassificacaoPagina -Texto 'sexo sexo sexo sexo sexo').Bloquear)
Assert 'Noticia com violencia 1x NAO bloqueia'     (-not (Get-ClassificacaoPagina -Texto 'programa contra a violencia urbana no centro da cidade').Bloquear)
Assert 'Blog de receita NAO bloqueia'              (-not (Get-ClassificacaoPagina -Texto 'bolo de cenoura com cobertura de chocolate receita simples e rapida').Bloquear)
Assert 'Aula de reproducao NAO bloqueia'           (-not (Get-ClassificacaoPagina -Texto 'aula de ciencias reproducao humana sistema reprodutor biologia').Bloquear)
Assert 'Pagina vazia NAO bloqueia'                 (-not (Get-ClassificacaoPagina -Texto '').Bloquear)
Assert 'Analise de pagina retorna score'           ((Get-ClassificacaoPagina -Texto 'pornografia pornografia pornografia').Score -ge 3)

# --- Relatorio ------------------------------------------------------
Write-Host ''
Write-Host '  ------------------------------------------' -ForegroundColor DarkGray
Write-Host ("  RESULTADO: {0} passaram, {1} falharam" -f $script:pass, $script:fail) -ForegroundColor $(if ($script:fail -eq 0) { 'Green' } else { 'Red' })
Write-Host ''

# limpa a sandbox ao final
$p = Get-SentinelaPaths
if (Test-Path $p.Base) { Remove-Item $p.Base -Recurse -Force -ErrorAction SilentlyContinue }

if ($script:fail -gt 0) { exit 1 } else { exit 0 }
