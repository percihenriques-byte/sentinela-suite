<#
    Sentinela-Classificador.ps1
    ------------------------------------------------------------------
    IA LOCAL de classificacao de conteudo. Roda 100% na maquina, SEM
    nenhuma API externa e sem internet. As buscas do filho NUNCA saem
    do computador (privacidade por design).

    O classificador:
      1. NORMALIZA o texto para derrotar tentativas de evasao:
         - tira acentos, desfaz leetspeak (p0rn0 -> porno),
         - junta letras espacadas (p o r n -> porn),
         - encolhe repeticoes (poooorno -> porno).
      2. PONTUA por tema, com pesos, e da um NIVEL DE CONFIANCA (0 a 1).
      3. E CONFIGURAVEL pelo responsavel (config.json, secao "classificador"):
         - temasDesativados : lista de temas para NAO bloquear
         - termosPersonalizados : palavras extras que o responsavel quer barrar
         - modoRigido : baixa o limiar e bloqueia de forma mais ampla
      4. Reduz falso-positivo em contexto educativo/saude (exceto temas que
         nunca sao "educativos", como burlar protecao).

    Uso:
      . .\Sentinela-Classificador.ps1
      Get-ClassificacaoConteudo -Texto 's3x0 +18'
    ------------------------------------------------------------------
#>

# ---- normalizacao ---------------------------------------------------
function ConvertTo-SemAcento {
    param([string]$Texto)
    if (-not $Texto) { return '' }
    $d = $Texto.Normalize([System.Text.NormalizationForm]::FormD)
    $sb = New-Object System.Text.StringBuilder
    foreach ($c in $d.ToCharArray()) {
        $cat = [System.Globalization.CharUnicodeInfo]::GetUnicodeCategory($c)
        if ($cat -ne [System.Globalization.UnicodeCategory]::NonSpacingMark) { [void]$sb.Append($c) }
    }
    return $sb.ToString()
}

function Get-TextoNormalizado {
    param([string]$Texto)
    $t = (ConvertTo-SemAcento $Texto).ToLowerInvariant()
    $mapa = @{ '0'='o'; '1'='i'; '3'='e'; '4'='a'; '5'='s'; '7'='t'; '8'='b'; '9'='g'; '@'='a'; '$'='s'; '+'='t' }
    foreach ($k in $mapa.Keys) { $t = $t.Replace($k, $mapa[$k]) }
    $t = [regex]::Replace($t, '(.)\1{2,}', '$1')
    $colado = [regex]::Replace($t, '[^a-z0-9]', '')
    return [pscustomobject]@{ Texto = $t; Colado = $colado }
}

# ---- base de conhecimento (pesos) ----------------------------------
# peso 1.0 = termo forte (sozinho ja bloqueia)  | 0.5 = medio  | 0.35 = fraco
# Padrao = $true  -> tema bloqueado por padrao
# Padrao = $false -> tema so bloqueia se o responsavel ativar
$script:CATEGORIAS = @(
    @{ Nome='Conteudo adulto'; Padrao=$true; SemReducao=$false; Termos=@{
        'porno'=1.0;'pornografia'=1.0;'pornografico'=1.0;'xvideos'=1.0;'xnxx'=1.0;'nudes'=1.0;'hentai'=1.0;
        'putaria'=1.0;'conteudo adulto'=1.0;'sexo explicito'=1.0;'onlyfans'=1.0;'camgirl'=1.0;
        'sexo'=0.5;'nudez'=0.5;'pelada'=0.5;'pelado'=0.5;'+18'=0.5;'nu'=0.35;'seios'=0.35 } },
    @{ Nome='Violencia'; Padrao=$true; SemReducao=$false; Termos=@{
        'decapitacao'=1.0;'tortura'=1.0;'gore'=1.0;'estupro'=1.0;'espancamento'=0.5;
        'violencia'=0.5;'sangue'=0.35;'briga'=0.35;'assassinato'=0.5;'massacre'=0.5 } },
    @{ Nome='Autolesao e suicidio'; Padrao=$true; SemReducao=$true; Termos=@{
        'suicidio'=1.0;'como se matar'=1.0;'automutilacao'=1.0;'me cortar'=1.0;'tirar a propria vida'=1.0;
        'anorexia dicas'=1.0;'pro ana'=1.0 } },
    @{ Nome='Armas'; Padrao=$true; SemReducao=$true; Termos=@{
        'como fazer bomba'=1.0;'fabricar arma'=1.0;'arma caseira'=1.0;'explosivo'=0.5;
        'pistola'=0.35;'rifle'=0.35;'municao'=0.35 } },
    @{ Nome='Drogas'; Padrao=$true; SemReducao=$false; Termos=@{
        'como usar drogas'=1.0;'comprar maconha'=1.0;'cocaina'=0.5;'crack'=0.5;'maconha'=0.5;
        'lsd'=0.5;'ecstasy'=0.5;'droga'=0.35;'entorpecente'=0.5 } },
    @{ Nome='Apostas'; Padrao=$true; SemReducao=$true; Termos=@{
        'cassino online'=1.0;'aposta esportiva'=1.0;'jogo do bicho'=1.0;'aposta'=0.5;'bet'=0.35;'cassino'=0.5;
        'tigrinho'=1.0;'jogo do tigrinho'=1.0 } },
    @{ Nome='Burlar protecao'; Padrao=$true; SemReducao=$true; Termos=@{
        'burlar filtro'=1.0;'burlar o filtro'=1.0;'driblar o filtro'=1.0;'desativar safesearch'=1.0;
        'desbloquear sites'=1.0;'filtro da escola'=1.0;'vpn para escola'=1.0;'como burlar'=0.5;'proxy anonimo'=0.5 } },
    @{ Nome='Linguagem impropria'; Padrao=$true; SemReducao=$true; Termos=@{
        'caralho'=0.5;'porra'=0.5;'buceta'=1.0;'piroca'=1.0;'xingamentos pesados'=0.5 } },
    # temas OPCIONAIS (o responsavel decide se ativa):
    @{ Nome='Namoro e relacionamento'; Padrao=$false; SemReducao=$true; Termos=@{
        'app de namoro'=1.0;'tinder'=1.0;'como beijar'=0.5;'namorada online'=0.5;'pegar meninas'=0.5 } },
    @{ Nome='Redes sociais'; Padrao=$false; SemReducao=$true; Termos=@{
        'tiktok'=0.5;'instagram'=0.5;'kwai'=0.5;'snapchat'=0.5;'como criar conta no'=0.35 } }
)

$script:CONTEXTO_SEGURO = @('dever de casa','trabalho escolar','feira de ciencias','aula de ciencias',
    'biologia','saude','medico','doenca','cancer','prevencao','sintomas','aula de')

$script:LIMIAR_PADRAO = 1.0

# ---- configuracao do responsavel -----------------------------------
# checagem de propriedade segura sob StrictMode (indexador nao enumera).
function Test-Prop {
    param($Obj, [string]$Nome)
    return ($null -ne $Obj -and $null -ne $Obj.PSObject.Properties[$Nome])
}

# Le a secao "classificador" do config.json, se o app estiver instalado.
function Get-ClassificadorConfig {
    if (Get-Command Get-SentinelaConfig -ErrorAction SilentlyContinue) {
        $cfg = Get-SentinelaConfig
        if (Test-Prop $cfg 'classificador') { return $cfg.classificador }
    }
    return $null
}

# ---- classificacao --------------------------------------------------
function Get-ClassificacaoConteudo {
    param([Parameter(Mandatory)][string]$Texto)
    $norm = Get-TextoNormalizado -Texto $Texto

    # configuracao do responsavel
    $conf = Get-ClassificadorConfig
    $desativados = @()
    $modoRigido  = $false
    $termosExtra = @()
    if ($conf) {
        if ((Test-Prop $conf 'temasDesativados') -and $conf.temasDesativados) { $desativados = @($conf.temasDesativados) }
        if (Test-Prop $conf 'modoRigido') { $modoRigido = [bool]$conf.modoRigido }
        if ((Test-Prop $conf 'termosPersonalizados') -and $conf.termosPersonalizados) { $termosExtra = @($conf.termosPersonalizados) }
    }
    $limiar = if ($modoRigido) { 0.5 } else { $script:LIMIAR_PADRAO }

    # reducao por contexto educativo/saude
    $reducao = 0.0
    foreach ($ctx in $script:CONTEXTO_SEGURO) {
        if ($norm.Texto.Contains((ConvertTo-SemAcento $ctx))) { $reducao = 0.5; break }
    }

    # monta a lista de temas ativos (+ tema personalizado do responsavel)
    $categorias = @()
    foreach ($cat in $script:CATEGORIAS) {
        if ($desativados -contains $cat.Nome) { continue }
        if (-not $cat.Padrao -and ($desativados -notcontains ('ATIVAR:' + $cat.Nome))) {
            # temas opcionais so entram se o responsavel ativou explicitamente
            if (-not ((Test-Prop $conf 'temasAtivados') -and (@($conf.temasAtivados) -contains $cat.Nome))) {
                continue
            }
        }
        $categorias += $cat
    }
    if ($termosExtra.Count -gt 0) {
        $mapaExtra = @{}
        foreach ($t in $termosExtra) { $mapaExtra[(ConvertTo-SemAcento ([string]$t)).ToLowerInvariant()] = 1.0 }
        $categorias += @{ Nome='Bloqueio do responsavel'; Padrao=$true; SemReducao=$true; Termos=$mapaExtra }
    }

    $melhor = $null
    foreach ($cat in $categorias) {
        $score = 0.0
        $sinais = @()
        foreach ($termo in $cat.Termos.Keys) {
            $peso = $cat.Termos[$termo]
            $termoColado = [regex]::Replace($termo, '[^a-z0-9]', '')
            if ($norm.Texto.Contains($termo) -or ($termoColado.Length -ge 3 -and $norm.Colado.Contains($termoColado))) {
                $score += $peso
                $sinais += $termo
            }
        }
        if ($score -gt 0) {
            $reducaoCat = if ($cat.SemReducao) { 0.0 } else { $reducao }
            $scoreFinal = [math]::Max(0.0, $score - $reducaoCat)
            if ($null -eq $melhor -or $scoreFinal -gt $melhor.Score) {
                $melhor = [pscustomobject]@{ Categoria=$cat.Nome; Score=$scoreFinal; Sinais=$sinais }
            }
        }
    }

    if ($null -eq $melhor) {
        return [pscustomobject]@{ Bloquear=$false; Categoria=$null; Confianca=0.0; Sinais=@(); Motivo='Nenhum sinal de risco.' }
    }

    $bloquear = ($melhor.Score -ge $limiar)
    $confianca = [math]::Round([math]::Min(1.0, $melhor.Score / ($limiar * 1.5)), 2)
    $motivo = if ($bloquear) {
        ('Tema "{0}" detectado (sinais: {1}).' -f $melhor.Categoria, ($melhor.Sinais -join ', '))
    } else {
        ('Sinais fracos de "{0}", abaixo do limiar - liberado.' -f $melhor.Categoria)
    }

    return [pscustomobject]@{
        Bloquear=$bloquear; Categoria=$melhor.Categoria; Confianca=$confianca; Sinais=$melhor.Sinais; Motivo=$motivo
    }
}

function Test-ConteudoImproprio {
    param([Parameter(Mandatory)][string]$Texto)
    return (Get-ClassificacaoConteudo -Texto $Texto).Bloquear
}

# lista os temas disponiveis (para o painel do responsavel montar as opcoes)
function Get-TemasDisponiveis {
    return $script:CATEGORIAS | ForEach-Object {
        [pscustomobject]@{ Tema=$_.Nome; PadraoLigado=$_.Padrao }
    }
}
