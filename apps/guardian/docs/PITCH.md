# 🛡️ Sentinela — Pitch

**Desafio Liga Jovem / SEBRAE**
*Busca segura à prova de incógnito.*

---

## 1. O problema

Toda família quer proteger a criança de conteúdo impróprio na internet. As ferramentas
que existem hoje têm uma **falha conhecida por qualquer criança de 10 anos**:

> O SafeSearch e a maioria dos filtros ficam **dentro do navegador**.
> Basta abrir uma **aba anônima** — ou instalar outro navegador — e o filtro **some**.

Ou seja: a proteção que os pais acham que têm **não existe** no momento em que mais
importa. Os filtros "de verdade" que resolvem isso são caros, complicados de instalar
e feitos para empresas e escolas — **não para uma família comum**.

## 2. A solução

O **Sentinela** tira a proteção de dentro do navegador e a coloca na **camada de rede**
do computador — o lugar por onde **toda** navegação passa, antes de qualquer navegador.

Ele força o **modo seguro** do Google, Bing e YouTube usando uma técnica real e
gratuita (DNS de filtro + `forcesafesearch`/`restrict.youtube.com`). Resultado:

| | SafeSearch comum | **Sentinela** |
|---|:---:|:---:|
| Funciona no Chrome | ✅ | ✅ |
| Funciona em outro navegador | ❌ | ✅ |
| Funciona no modo anônimo | ❌ | ✅ |
| A criança consegue desligar | ✅ (1 clique) | ❌ (só com PIN) |
| Religa sozinho se adulterado | ❌ | ✅ (Guardião) |
| Fácil de instalar em casa | — | ✅ (1 clique) |
| Custo para a família | — | **grátis** |

## 3. Por que é difícil de burlar

Três camadas trabalhando juntas:

1. **DNS de filtro** — muda para onde o computador "pergunta" os endereços, forçando
   o modo seguro em toda a rede.
2. **Arquivo hosts** — reforço local que continua valendo mesmo se alguém trocar o DNS.
3. **Guardião** — uma tarefa do sistema que verifica a cada 1 minuto e **reaplica** a
   proteção se ela for removida. Só o **PIN do responsável** desliga de verdade.

> **Honestidade:** nenhum filtro é 100% inviolável para um adulto especialista (dá para
> usar VPN, outro sistema, etc.). O Sentinela fecha o **caminho fácil** — o que hoje
> qualquer criança usa — e é isso que muda o jogo para a família.

## 3½. A IA local (anti-evasão)

O bloqueio de rede é category-agnostic (o próprio Google aplica o modo seguro). Para o
**painel e a análise**, o Sentinela usa uma **IA que roda na própria máquina** — sem
internet, sem API paga, sem enviar as buscas das crianças para nenhum servidor
(privacidade por design). Ela não depende de "palavras exatas": normaliza o texto para
derrotar as fugas clássicas das crianças —

| Tentativa de driblar | Filtro de lista | **IA local do Sentinela** |
|---|:---:|:---:|
| `pornografia` | pega | pega |
| `p0rn0` / `s3x0` (números) | passa ❌ | **pega** ✅ |
| `p o r n o` (espaçado) | passa ❌ | **pega** ✅ |
| `poooorno` (repetição) | passa ❌ | **pega** ✅ |
| "câncer de mama" (saúde) | bloqueia por engano ❌ | **libera** ✅ (entende o contexto) |

Cada decisão vem com uma **categoria**, um **nível de confiança** e os **sinais** que
pesaram — dá para explicar aos pais *por que* algo foi bloqueado.

**A IA vive em dois lugares:** (1) na **extensão do navegador**, que bloqueia a busca na
hora e cobre temas que o modo seguro não pega (apostas, autolesão, violência); e (2) no
app, para a análise e a supervisão. O responsável escolhe os temas e adiciona palavras.

## 3¾. Supervisão (fiscalização)

O Sentinela **registra o que a criança busca** — tema, nível de confiança e horário — e
mostra para o responsável (no popup da extensão ou no painel do app), com as buscas
bloqueadas em destaque e um resumo por tema. **Tudo local**: as buscas do filho nunca
saem do computador. Não é espionagem escondida — é uma ferramenta **transparente de
controle parental**, instalada pelo responsável.

## 4. Mercado

- **74 milhões** de brasileiros com menos de 18 anos; a maioria acessa a internet.
- Preocupação dos pais com segurança digital infantil só cresce (escola, celular, tablet).
- Concorrentes (Qustodio, Norton Family, Google Family Link) são **pagos**, focados em
  monitoramento e **não fecham a brecha do modo anônimo na busca**.
- Nosso nicho inicial: **famílias e pequenas escolas** que querem algo **simples e grátis**
  para começar.

## 5. Modelo de negócio

Começa **gratuito e de código aberto** (ganha confiança e adoção). Receita depois via:

- **Sentinela Plus** (assinatura baixa, ~R$ 9,90/mês): painel na nuvem para acompanhar
  vários aparelhos, relatórios semanais por e-mail, recuperação de PIN, listas
  personalizadas.
- **Sentinela Escola**: licença para laboratórios de informática de escolas pequenas.
- Parcerias com provedores de internet regionais (DNS de filtro como serviço opcional).

## 6. Roteiro (roadmap)

- ✅ **MVP Windows** — instalador 1 clique, PIN, Guardião, painel (este projeto).
- 🔜 **Assistente de celular** — guia para configurar DNS de filtro no Wi-Fi de casa.
- 🔜 **Painel na nuvem** — acompanhar vários aparelhos, relatórios para os pais.
- ✅ **IA local anti-evasão** — classificador que roda na máquina, entende tentativas de
  driblar (leetspeak, letras espaçadas) e o contexto educativo (neste projeto).
- ✅ **Extensão travada por política** — force-install (`ExtensionInstallForcelist`) para
  Edge/Chrome, servido por um **servidor local `127.0.0.1`** (sem internet): a criança
  não consegue desativar (mesmo mecanismo das escolas).
- 🔜 **IA na nuvem opcional** — modelo maior para categorização ainda mais fina no painel.
- 🔜 **App de roteador** — proteção para a casa inteira num só lugar.

## 7. Por que nós

Projeto criado por um jovem estudante que **viveu o problema**: viu como é fácil
burlar os filtros da escola e resolveu construir algo que realmente funciona — simples
o bastante para a própria família usar. Tecnologia real, honesta e acessível.

---

### Demonstração

- **Demo web navegável** (`demo/index.html`): deixe o jurado *tentar burlar* e ver o
  filtro segurar, ao vivo.
- **App real** (`app/`): instala e funciona de verdade no Windows.
- **Testes** (`app/Testes/`): 21 verificações automatizadas, todas passando.

> **Sentinela — o filtro de hoje desliga sozinho. O nosso, não.**
