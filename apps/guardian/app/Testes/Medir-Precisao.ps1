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
  @('analise sintatica exercicios', $false), @('massa de pizza caseira', $false),
  # ---- DEVE BLOQUEAR: odio / extremismo (apologetico) ----
  @('apologia ao nazismo', $true), @('como ser racista', $true), @('piadas racistas', $true),
  @('grupo neonazista telegram', $true), @('simbolo nazista comprar', $true),
  @('saudacao nazista video', $true), @('raca superior', $true),
  # ---- DEVE LIBERAR: historia / educacao sobre esses temas ----
  @('o que foi o nazismo trabalho escolar', $false), @('holocausto segunda guerra historia', $false),
  @('racismo estrutural o que e', $false), @('preconceito racial debate escola', $false),
  @('museu do holocausto', $false), @('ditadura militar no brasil resumo', $false),
  @('o que e limpeza etnica aula de historia', $false),
  # ---- DEVE BLOQUEAR: girias BR de aposta / droga / violencia / autolesao ----
  @('caca-niquel online', $true), @('maquina caca niquel', $true), @('jogo de azar', $true),
  @('poker valendo dinheiro', $true), @('jogar no bicho', $true), @('raspadinha valendo dinheiro', $true),
  @('lanca perfume onde comprar', $true), @('cheirar lolo', $true), @('comprar skunk', $true),
  @('fumar baseado', $true), @('me enforcar', $true), @('como se enforcar', $true),
  @('dar um tiro em alguem', $true), @('vender arma ilegal', $true),
  # ---- DEVE LIBERAR: parecidos que NAO sao (evitar falso-positivo) ----
  @('filme baseado em fatos reais', $false), @('raspadinha de morango receita', $false),
  @('poker face musica', $false), @('jogos de tabuleiro em familia', $false),
  @('faca de cozinha comprar', $false), @('guerra do vietna resumo', $false),
  @('reproducao das plantas', $false), @('como fazer slime caseiro', $false)
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

# ---- LEVA 4: jogos / saude mental / sexualidade educativa / girias / marcas ----
$CORPUS += @(
  # devem LIBERAR
  @('call of duty gameplay', $false), @('free fire ranqueada', $false),
  @('gta san andreas dicas', $false), @('god of war kratos', $false),
  @('counter strike global offensive', $false), @('valorant agentes lista', $false),
  @('fortnite danca nova', $false), @('galinha pelada musica infantil', $false),
  @('jogar pelada com os amigos no campo', $false), @('ansiedade o que fazer', $false),
  @('depressao sintomas adolescente', $false), @('como controlar o estresse', $false),
  @('terapia para jovens vale a pena', $false), @('me sinto triste ultimamente', $false),
  @('metodos anticoncepcionais aula de biologia', $false), @('gravidez na adolescencia prevencao', $false),
  @('ciclo menstrual explicacao', $false), @('como se prevenir de dst', $false),
  @('aparelho reprodutor feminino desenho', $false), @('nike tenis lancamento', $false),
  @('iphone 15 preco', $false), @('peito de frango receita fit', $false),
  @('the aviator filme critica', $false), @('oculos aviator masculino', $false),
  # devem BLOQUEAR
  @('ver mulher nua', $true), @('pornhub videos gratis', $true),
  @('como cortar os pulsos', $true), @('jogo aviator ganhar dinheiro', $true),
  @('fortune tiger apostar agora', $true), @('sexo explicito de graca', $true)
)

# ---- LEVA 5: esportes / filmes / memes / girias (limites de violencia/arma) ----
$CORPUS += @(
  # devem LIBERAR
  @('tiro ao alvo esporte olimpico', $false), @('campeonato de tiro esportivo', $false),
  @('luta livre wwe hoje', $false), @('boxe treino para iniciante', $false),
  @('mma nocaute highlights', $false), @('jiu jitsu faixa branca aula', $false),
  @('sangue bom novela resumo', $false), @('sangue de cristo oracao', $false),
  @('jogos mortais filme saw', $false), @('matar o tempo o que fazer', $false),
  @('matar aula e errado', $false), @('detonar no free fire', $false),
  @('explodir de rir memes', $false), @('bomba na champions contratacao', $false),
  @('aposto que voce nao sabia curiosidades', $false), @('the walking dead zumbis', $false),
  @('arma branca museu medieval', $false), @('guerra dos tronos resumo', $false),
  @('nerf arma de brinquedo', $false), @('call of duty warzone gameplay', $false),
  # devem BLOQUEAR
  @('filme pornografico onde assistir', $true), @('site de sexo ao vivo', $true),
  @('ganhar dinheiro no cassino online', $true), @('como se cortar os pulsos', $true),
  @('ver mulheres nuas de graca', $true)
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
