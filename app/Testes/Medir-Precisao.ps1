<#
    Medir-Precisao.ps1
    ------------------------------------------------------------------
    Roda um corpus rotulado pelo classificador e mede a acuracia,
    listando falsos-positivos (bloqueou o que era legitimo) e
    falsos-negativos (deixou passar o que era improprio).

    Uso:  .\Medir-Precisao.ps1
    Corpus em ASCII de proposito (o .ps1 e lido como ANSI; o classificador
    normaliza acentos de qualquer forma). Casos de evasao unicode entram
    por codigo.
    ------------------------------------------------------------------
#>
$env:SENTINELA_SIMULAR = '1'
$appDir = Split-Path $PSScriptRoot -Parent
. (Join-Path $appDir 'Sentinela-Core.ps1')
. (Join-Path $appDir 'Sentinela-Pin.ps1')
. (Join-Path $appDir 'Sentinela-Classificador.ps1')
$p = Get-SentinelaPaths; if (Test-Path $p.Base) { Remove-Item $p.Base -Recurse -Force }
Initialize-SentinelaStore | Out-Null
Save-SentinelaConfig -Config ([pscustomobject]@{}) | Out-Null

# [texto, deveBloquear]   (busca)
$CORPUS = @(
  # ---- DEVE BLOQUEAR: adulto ----
  @('pornografia', $true), @('porno', $true), @('sexo', $true), @('video de sexo', $true),
  @('fazer sexo', $true), @('sexo explicito', $true), @('xvideos', $true), @('xnxx', $true),
  @('hentai', $true), @('nudez', $true), @('mulher pelada', $true), @('fotos de nudez', $true),
  @('transar', $true), @('zoofilia', $true), @('onlyfans vazado', $true), @('putaria', $true),
  @('masturbacao', $true), @('sexo gratis', $true), @('ver gente transando', $true),
  # ---- DEVE BLOQUEAR: apostas ----
  @('bet365', $true), @('aposta esportiva', $true), @('cassino online', $true),
  @('jogo do tigrinho', $true), @('blaze aposta', $true), @('betano', $true), @('roleta cassino', $true),
  # ---- DEVE BLOQUEAR: violencia / autolesao / armas / drogas ----
  @('video de violencia extrema', $true), @('decapitacao', $true), @('tortura real', $true),
  @('briga de rua', $true), @('como se matar', $true), @('quero morrer', $true),
  @('metodos de me cortar', $true), @('como fazer uma bomba', $true), @('arma caseira', $true),
  @('como usar cocaina', $true), @('comprar maconha', $true),
  # ---- DEVE BLOQUEAR: burlar / linguagem ----
  @('como burlar o filtro da escola', $true), @('desativar safesearch', $true),
  # ---- DEVE BLOQUEAR: evasao ----
  @('s3x0', $true), @('p0rn0', $true), @('p o r n o', $true), @('poooorno', $true),

  # ---- DEVE LIBERAR: educativo / saude (os dificeis!) ----
  @('reproducao humana', $false), @('sistema reprodutor', $false), @('puberdade', $false),
  @('menstruacao o que e', $false), @('cancer de mama sintomas', $false),
  @('educacao sexual na escola', $false), @('doencas sexualmente transmissiveis', $false),
  @('sexo masculino ou feminino', $false), @('qual o sexo do bebe', $false),
  @('diferenca entre sexo masculino e feminino biologia', $false),
  @('anatomia do corpo humano', $false), @('como funciona a gravidez', $false),
  @('violencia domestica onde denunciar', $false), @('historia da segunda guerra mundial', $false),
  @('efeitos das drogas trabalho escolar', $false), @('o que e bullying', $false),
  @('saude mental adolescente ajuda', $false), @('cvv centro de valorizacao da vida', $false),
  # ---- DEVE LIBERAR: comum / jogos / escola ----
  @('receita de bolo de cenoura', $false), @('minecraft como construir casa', $false),
  @('roblox jogos gratis', $false), @('exercicios de matematica 9 ano', $false),
  @('vulcao para feira de ciencias', $false), @('filhotes de golden retriever', $false),
  @('tabela periodica', $false), @('como desenhar anime', $false),
  @('musica infantil', $false), @('assistir desenho', $false), @('jogos de tabuleiro', $false),
  @('apostila de portugues', $false), @('menu do restaurante', $false),
  @('numero de telefone da escola', $false), @('aprender o alfabeto', $false),
  @('alfabeto para criancas', $false), @('betoneira preco', $false),
  @('classico do brasileirao ontem', $false), @('violao aula para iniciantes', $false),
  @('assexuado significado biologia', $false), @('sexta-feira feriado', $false),
  @('analise sintatica exercicios', $false), @('massa de pizza caseira', $false)
)

# evasao unicode por codigo
$CORPUS += ,@(('p' + [char]0x043E + 'rn' + [char]0x043E), $true)                 # porno cirilico
$CORPUS += ,@([string]([char]0xFF53 + [char]0xFF45 + [char]0xFF58 + [char]0xFF4F), $true) # sexo full-width

# ---- LEVA CEGA (holdout): casos novos p/ detectar overfitting/regressao ----
$CORPUS += @(
  # devem BLOQUEAR
  @('ver pornografia gratis', $true), @('site pornografico', $true), @('video porno', $true),
  @('sexo com animais', $true), @('quero me matar hoje', $true),
  @('como fazer explosivo caseiro', $true), @('site de apostas online', $true),
  @('fotos de mulheres peladas', $true), @('conteudo adulto +18 gratis', $true),
  # devem LIBERAR (armadilhas)
  @('receita de bomba de chocolate', $false), @('bomba de chocolate caseira', $false),
  @('bomba de agua para poco', $false), @('roleta russa filme critica', $false),
  @('transferencia bancaria transacao', $false), @('sexo dos anjos significado', $false),
  @('sexta serie do fundamental', $false), @('loja de brinquedos perto', $false),
  @('documentario sobre a guerra do vietna', $false), @('filme de terror recomendacao', $false),
  @('sangue nas fezes o que pode ser', $false), @('violencia contra a mulher lei maria da penha', $false),
  @('desenho para colorir gratis', $false), @('bomba de encher pneu de bicicleta', $false),
  @('aposta de quem chega primeiro brincadeira', $false), @('sexo fragil expressao', $false)
)

# ---- LEVA 3: LGBT / saude / arte / historia / jogos / social ----
$CORPUS += @(
  # devem LIBERAR
  @('o que e ser gay', $false), @('bandeira lgbt significado', $false),
  @('casamento homossexual e legal no brasil', $false), @('transexualidade o que e', $false),
  @('orientacao sexual definicao', $false), @('identidade de genero explicacao', $false),
  @('sexualidade na adolescencia texto', $false), @('camisinha como usar corretamente', $false),
  @('primeira menstruacao o que fazer', $false), @('corrimento o que pode ser', $false),
  @('puberdade nos meninos mudancas', $false), @('espinhas na adolescencia tratamento', $false),
  @('estatua grega nudez arte historia', $false), @('arte renascentista corpo humano museu', $false),
  @('segunda guerra mundial resumo escola', $false), @('holocausto o que foi historia', $false),
  @('escravidao no brasil resumo', $false), @('revolucao francesa causas', $false),
  @('free fire personagens novos', $false), @('gta 5 missoes lista', $false),
  @('among us como jogar', $false), @('stumble guys dicas', $false),
  @('como fazer amigos na escola', $false), @('primeiro beijo dicas', $false),
  @('sistema genital masculino aula de biologia', $false), @('palestra sobre bullying escola', $false),
  @('violencia no transito estatisticas', $false), @('filme de acao com tiros recomendacao', $false),
  # devem BLOQUEAR
  @('ver buceta', $true), @('sexo na webcam ao vivo', $true), @('novinha pelada', $true),
  @('apostar na blaze', $true), @('onlyfans gratis vazado', $true),
  @('como cheirar cola para chapar', $true), @('comprar arma de fogo ilegal', $true),
  @('comprar armario de cozinha', $false)
)

$fp = @(); $fn = @(); $ok = 0
foreach ($caso in $CORPUS) {
  $r = Get-ClassificacaoConteudo -Texto $caso[0]
  if ($r.Bloquear -eq $caso[1]) { $ok++ }
  elseif ($r.Bloquear -and -not $caso[1]) { $fp += ('"{0}"  -> {1}' -f $caso[0], $r.Categoria) }
  else { $fn += ('"{0}"' -f $caso[0]) }
}
$total = $CORPUS.Count
Write-Host ''
Write-Host ("  CORPUS: {0} casos  |  acertos: {1}  |  acuracia: {2}%" -f $total, $ok, [math]::Round(100.0*$ok/$total,1)) -ForegroundColor Cyan
Write-Host ("  Falsos-POSITIVOS (bloqueou legitimo): {0}" -f $fp.Count) -ForegroundColor $(if($fp.Count){'Red'}else{'Green'})
$fp | ForEach-Object { Write-Host ("     x " + $_) -ForegroundColor Red }
Write-Host ("  Falsos-NEGATIVOS (deixou passar): {0}" -f $fn.Count) -ForegroundColor $(if($fn.Count){'Yellow'}else{'Green'})
$fn | ForEach-Object { Write-Host ("     ! " + $_) -ForegroundColor Yellow }
Write-Host ''
