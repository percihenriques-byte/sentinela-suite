# 🧠 Adicionar um modelo de imagem treinado (opcional, mais preciso)

O Sentinela já analisa imagens com um **heurístico local** (proporção de tom de pele,
em `analise-imagem.js`). Ele é offline e sem download, mas **cru** — pode deixar passar
ou borrar por engano. Para uma análise **precisa**, dá para plugar um modelo de IA
treinado que roda **localmente** no navegador (sem internet, sem servidor).

## Recomendado: NSFWJS (TensorFlow.js)

O [NSFWJS](https://github.com/infinitered/nsfwjs) classifica imagens em categorias
(neutro, sexy, porn, hentai, desenho) usando um modelo pequeno que roda no próprio
navegador. É open-source e gratuito.

### Passo a passo (uma vez)

1. Baixe os arquivos (num computador com internet):
   - A biblioteca **TensorFlow.js** (`tf.min.js`).
   - A biblioteca **NSFWJS** (`nsfwjs.min.js`).
   - Os arquivos do **modelo** (`model.json` + os `.bin` de pesos, ~4 MB).
2. Coloque todos dentro desta pasta `modelo/` da extensão.
3. Me avise (ou edite `background.js`): troco o heurístico pela chamada do NSFWJS —
   o `background.js` já está preparado para isso (a função `analisarImagemUrl` só precisa
   chamar o modelo em vez de `SentinelaImg.analisarPixels`).

> **Por que você precisa baixar:** os arquivos do modelo têm alguns MB de binário e
> **não podem ser buscados de um servidor externo** em tempo de execução (a regra do
> projeto é zero APIs/fetch externo, e a CSP da extensão bloqueia CDNs). Por isso eles
> ficam **embutidos** na extensão, baixados uma única vez por você.

## Enquanto não houver modelo

A extensão usa o heurístico automaticamente. Você pode **ligar/desligar** a análise de
imagens no popup da extensão (aba *Configurar temas* → *Analisar imagens*).
