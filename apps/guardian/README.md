# 🛡️ Sentinela — busca segura à prova de incógnito

Projeto para o **Desafio Liga Jovem / SEBRAE**.

O Sentinela é um controle de conteúdo para crianças que **não vive dentro do navegador** —
por isso o modo anônimo (incógnito) não consegue desligá-lo. Ele força o **modo seguro**
do Google, Bing e YouTube na **camada de rede (DNS)** do computador, e só pode ser
desativado com o **PIN do responsável**.

---

## O problema

O SafeSearch comum guarda a configuração no navegador. Basta abrir uma **aba anônima**
(ou instalar outro navegador) e o filtro simplesmente some. Qualquer criança descobre isso.

## A solução

O Sentinela move a proteção para **antes** do navegador:

```
[ App Sentinela instalado no PC ]
        ↓ trava o DNS do sistema + arquivo hosts
  google.com   → forcesafesearch.google.com
  youtube.com  → restrict.youtube.com
  bing.com     → strict.bing.com
        ↓
✓ vale em Chrome, Edge, Firefox, qualquer navegador
✓ vale no modo incógnito (não há o que desligar no navegador)
✓ só destrava com o PIN do responsável
✓ um "guardião" reaplica a config se alguém tentar mexer
```

Essa técnica (`forcesafesearch` / `restrict.youtube.com`) é **real** e é a mesma usada por
escolas e provedores. **Não depende de nenhuma API externa nem de servidor pago.**

### Duas camadas + supervisão

1. **Camada de rede (DNS + hosts)** — força o modo seguro do Google/YouTube/Bing em
   qualquer navegador, até no incógnito. Trava por PIN, com Guardião anti-adulteração.
2. **Camada de IA local (extensão do navegador)** — analisa **o que a criança vê**, na
   própria máquina (sem internet):
   - a **busca** e o **texto da página** (bloqueia páginas com conteúdo impróprio, por
     ocorrências, com limiar alto para não pegar menção incidental);
   - as **imagens** da página (borra as suspeitas via heurístico local: maior região
     conexa de tom de pele + suavidade; encaixe pronto para um modelo treinado);
   - entende tentativas de driblar (`p0rn0`, `p o r n o`, homóglifos, full-width) e o
     contexto legítimo (biologia, arte, saúde). O responsável escolhe os temas e adiciona
     palavras. Precisão medida: **100%** num corpus de 147 casos difíceis.
3. **Supervisão** — a extensão **registra o que a criança busca** (tema, confiança, hora)
   para o responsável revisar no popup da extensão ou no painel. Tudo fica **local**;
   nada é enviado para a internet (privacidade por design).

---

## O que tem neste repositório

| Pasta | O que é |
|-------|---------|
| [`demo/`](demo/) | **Demo web navegável** — o pitch visual para a apresentação. Deixa o jurado "tentar burlar" e ver o filtro segurar. |
| [`app/`](app/) | **Produto real** — scripts PowerShell que aplicam o filtro de DNS + hosts, com trava por PIN e guardião anti-adulteração. Roda em qualquer Windows sem instalar nada extra. |
| [`app/gui/`](app/gui/) | Painel do responsável (janela simples para ativar/desativar e definir o PIN). |
| [`docs/`](docs/) | Guia de instalação para leigos e material de apresentação. |

---

## Por que PowerShell (e não um .exe gigante)?

Todo Windows já vem com PowerShell instalado. Isso torna a instalação **acessível para
todos** (o requisito do projeto): não é preciso baixar Python, Node nem runtime nenhum.
O instalador pede o acesso de administrador uma vez, aplica a proteção e registra o
guardião. É o caminho mais simples que ainda é **de verdade**.

## Honestidade de engenharia

Nenhum filtro é 100% "impossível de burlar" para um adulto determinado (dá para trocar de
sistema operacional, usar VPN, etc.). O objetivo do Sentinela é ser **robusto o bastante
para a faixa etária alvo** — travar o caminho fácil (aba anônima, trocar de navegador,
mexer nas configurações) que hoje deixa o SafeSearch comum inútil.

---

## Estrutura do projeto

```
sentinela/
├── demo/
│   └── index.html              Demo web navegável (o pitch visual)
├── app/
│   ├── INSTALAR.bat            ← duplo clique para instalar (leigos)
│   ├── Instalar-Sentinela.ps1  Instalador: eleva admin, PIN, guardião, ativa
│   ├── Desinstalar-Sentinela.ps1  Remove tudo (exige PIN)
│   ├── Ativar-Sentinela.ps1    Liga a proteção
│   ├── Desativar-Sentinela.ps1 Desliga (exige PIN)
│   ├── Sentinela-Status.ps1    Mostra o estado atual
│   ├── Sentinela-Core.ps1      Núcleo: DNS de filtro + bloco hosts
│   ├── Sentinela-Pin.ps1       Trava por PIN (SHA-256 + salt)
│   ├── Sentinela-Guardiao.ps1  Reaplica a proteção se adulterada
│   ├── Sentinela-Classificador.ps1  IA local anti-evasão, configurável
│   ├── Sentinela-Supervisao.ps1  Registro do que foi buscado (fiscalização)
│   ├── Classificar-Busca.ps1   Ferramenta p/ o responsável testar a IA
│   ├── Ver-Supervisao.ps1      Ver/importar o registro de supervisão
│   ├── extensao/               Extensão Chrome/Edge: bloqueio por IA + captura
│   │   ├── manifest.json  content.js  classificador.js  popup.html  popup.js
│   │   ├── background.js       Service worker (análise de imagem cross-origin)
│   │   ├── analise-imagem.js   Heurístico local de imagem (tom de pele)
│   │   ├── modelo/             Encaixe para um modelo treinado (opcional)
│   │   └── COMO-INSTALAR-EXTENSAO.md
│   ├── TRAVAR-EXTENSAO.bat     ← trava a extensão (force-install)
│   ├── Travar-Extensao.ps1     Aplica ExtensionInstallForcelist (Edge+Chrome)
│   ├── Sentinela-Crx.ps1       Empacota .crx e calcula o ID da extensão
│   ├── Sentinela-Servidor.ps1  Servidor local 127.0.0.1 (serve update.xml + .crx)
│   ├── gui/
│   │   └── Sentinela-Painel.ps1   Painel gráfico (status, PIN, supervisão)
│   └── Testes/
│       ├── Executar-Testes.ps1    116 testes automatizados (simulação)
│       ├── Medir-Precisao.ps1     acurácia do classificador (corpus de 268 casos, PT+EN)
│       └── img-corpus.html        teste do heurístico de imagem
└── docs/
    ├── COMO-INSTALAR.md        Guia passo a passo para leigos
    ├── PITCH.md                Material de apresentação (SEBRAE)
    └── PLANO.md                Roteiro de construção
```

## Como testar sem alterar nada na máquina

Todos os scripts têm **modo simulação** (`-Simular`): usam uma pasta temporária e
**não** tocam no DNS/hosts reais. Rode a suíte de testes:

```powershell
.\app\Testes\Executar-Testes.ps1
```

Saída esperada: `RESULTADO: 116 passaram, 0 falharam`.

Para medir a **acurácia** do classificador num corpus de 147 casos difíceis:

```powershell
.\app\Testes\Medir-Precisao.ps1
```

Saída esperada: `acuracia: 100%` (0 falsos-positivos, 0 falsos-negativos).

Para testar só a IA local de classificação (inclui tentativas de evasão):

```powershell
.\app\Classificar-Busca.ps1 -Texto 's3x0 expl1c1t0'
```

Para experimentar o instalador em simulação:

```powershell
.\app\Instalar-Sentinela.ps1 -Simular
.\app\Sentinela-Status.ps1 -Simular
```

## Instalação de verdade

Veja o guia passo a passo em [`docs/COMO-INSTALAR.md`](docs/COMO-INSTALAR.md).
Resumo: dê dois cliques em `app/INSTALAR.bat`, clique **SIM** no aviso do Windows,
crie o PIN. Pronto.

## Demo online

Versão publicada da demo (link compartilhável para o pitch):

https://claude.ai/code/artifact/fd0c34ea-3d06-41b3-86c5-99d0040e34d6

> Arquivo-fonte: `demo/sentinela-artifact.html` (versão adaptada de `demo/index.html`
> para o formato Artifact — fontes do sistema, sem dependências externas).
