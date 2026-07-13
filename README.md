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

## Status

Em construção ativa. Veja [`docs/PLANO.md`](docs/PLANO.md) para o roteiro.
