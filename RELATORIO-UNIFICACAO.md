# Relatório — unificação Sentinela + VisiQuost

**Repositório:** `percihenriques-byte/sentinela-suite` (privado)
**Data:** 06/08/2026 · **Branch:** `main` · **105 commits**

Documento para quem vai continuar o projeto sem ter estado na sessão. Descreve
o que existia, o que foi feito, por que cada decisão foi tomada, o que foi
provado com teste e o que ficou em aberto.

---

## 1. Ponto de partida

Dois repositórios sem nenhum código em comum:

| | `percihenriques-byte/sentinela` | `percihenriques-byte/visiquost-crm` |
|---|---|---|
| O que é | Controle parental à prova de incógnito (Desafio Liga Jovem / SEBRAE) | CRM local com o assistente Jarvis |
| Stack | PowerShell (Windows) + extensão Chrome MV3 + página de pitch | FastAPI + SQLModel + SQLite + SPA em JS puro |
| Testes | 139 na suíte + corpus de 373 casos | 434 pytest |
| Regra dura | zero APIs externas | zero APIs externas |

**Objetivo recebido:** transformar os dois num único projeto, com a **UX oficial
do Sentinela**, sem perder nenhuma funcionalidade útil e sem grandes mudanças de
uma vez — só integrações pequenas e validadas.

**Leitura do problema.** Os dois produtos não têm sobreposição funcional: um
filtra conteúdo para crianças, o outro gerencia clientes. Unir "na marra" (fundir
telas ou modelos) destruiria os dois. O que eles têm em comum é o que importava:
ambos rodam **100% na máquina do usuário, sem nuvem**. Então a união foi feita
onde ela gera valor real:

- **uma casca só** (um servidor local, uma SPA, um login, um instalador, um
  repositório) — e essa casca é o **Sentinela**, com o CRM como seção interna;
- **uma identidade visual só** (a do Sentinela);
- **o CRM emprestando ao Sentinela a infraestrutura que ele não tinha**: banco,
  autenticação, criptografia em repouso, backup e uma interface web decente.

O Sentinela ganhou um painel web de verdade. O CRM não perdeu nada.

---

## 2. Estrutura final

```
sentinela-suite/
├── INICIAR.bat            sobe a suite  (http://127.0.0.1:8000)
├── INSTALAR.bat           instala tudo  (delega ao instalador do CRM)
├── README.md
├── apps/
│   ├── guardian/          ← era o repo sentinela
│   │   ├── app/           scripts PowerShell, extensao/, gui/, Testes/
│   │   ├── demo/          página de pitch (auto-contida)
│   │   └── docs/
│   └── crm/               ← era o repo visiquost-crm
│       ├── backend/       FastAPI, alembic/, tests/, scripts/
│       ├── frontend/      SPA (index.html + assets/)
│       └── docs/
└── packages/
    └── ui/                design system Sentinela — fonte única de tokens
```

### Como as peças conversam

```
    navegador da crianca            PC da familia
    ┌──────────────────┐        ┌──────────────────────┐
    │ extensao MV3     │        │ app PowerShell       │
    │ IA local: busca, │        │ DNS + hosts +        │
    │ texto e imagem   │        │ politica + PIN       │
    └────────┬─────────┘        └──────────┬───────────┘
             │ eventos (token)             │ eventos (token)
             └──────────────┬──────────────┘
                            ▼
              ┌───────────────────────────┐
              │  servidor local :8000     │
              │  FastAPI + SQLite         │
              │  /api/v1/sentinela/*      │
              │  /api/v1/...  (CRM)       │
              └────────────┬──────────────┘
                           ▼
              ┌───────────────────────────┐
              │  SPA unica                │
              │  Painel do responsavel    │
              │  + CRM, mesma UX          │
              └───────────────────────────┘
```

**Decisão importante:** o servidor **não** classifica conteúdo. A regra de
classificação tem uma fonte de verdade (`Sentinela-Classificador.ps1`) espelhada
em JS na extensão (`classificador.js`). Colocar uma terceira cópia no Python
criaria três lugares para divergir. O servidor guarda o **veredito** de quem
observou.

---

## 3. O que foi entregue, na ordem em que foi feito

Cada item foi implementado, validado e commitado antes do próximo.

### 3.1 Monorepo com histórico preservado

Os dois repositórios foram unidos preservando os 89 commits originais.

Detalhe técnico que vale registrar: a primeira tentativa usou `git read-tree
--prefix`, que funciona mas deixa os commits antigos **alcançáveis e ao mesmo
tempo invisíveis** para `git log <arquivo novo>` — o caminho do arquivo muda no
commit de merge e a travessia para ali. Refiz reescrevendo os dois históricos com
o prefixo do monorepo (`git filter-branch --index-filter`) **antes** da união.

Resultado: `git log` e `git blame` em qualquer arquivo mostram a vida inteira
dele. Verificação:

```bash
git log --oneline -- apps/guardian/app/Sentinela-Classificador.ps1   # 19 commits
git log --oneline -- apps/crm/backend/app/main.py                    # ate o "Initial commit"
```

A árvore de trabalho depois da reescrita ficou **byte a byte idêntica** à de
antes (conferida com `git diff` contra a branch `backup-antes-reescrita`, que
está publicada como rede de segurança).

### 3.2 Design system — a UX do Sentinela virou a UX da suite

`packages/ui/sentinela-tokens.css` é a fonte única de paleta, tipografia, raios,
sombras e movimento. Os valores saíram de `apps/guardian/demo/index.html`, a UX
oficial do Sentinela:

| Token | Valor | Papel |
|---|---|---|
| `--sn-ink` | `#0b1220` | fundo mais profundo |
| `--sn-panel` | `#0d1a26` | cartão / painel |
| `--sn-teal` | `#2dd4bf` | ação primária |
| `--sn-mint` | `#7ff5e6` | hover / realce |
| `--sn-coral` | `#ff6b6b` | perigo / bloqueio |
| `--sn-amber` | `#f6b73c` | alerta / incógnito |

**A jogada que fez o re-skin ser barato:** o pacote expõe os tokens da marca
**com os mesmos nomes de variável que o CRM já usava** (`--bg`, `--primary`,
`--danger`…), como apelidos. Por isso o CRM inteiro mudou de identidade visual
**sem uma linha de layout alterada**. O `app.css` perdeu os blocos `:root` e
`[data-theme="light"]` duplicados e passou a só consumir variáveis.

Também: escudo do Sentinela substituiu o círculo roxo (favicon, hero, sidebar);
cores cravadas (roxo, índigo, esmeralda) viraram tokens; a rampa categórica do
kanban foi reancorada no teal; tema claro ganhou variante coerente com a marca.

Sem CDN de fontes — a suite roda offline. Sora e DM Sans entram se estiverem
instaladas; senão a pilha cai para a fonte nativa do sistema.

### 3.3 Módulo Sentinela na API local

Novos arquivos em `apps/crm/backend`:

- `app/models/sentinela.py` — `SentinelaEvent` e `SentinelaConfig`
- `app/services/sentinela_service.py` — regras de negócio
- `app/api/routes_sentinela.py` — rotas
- `alembic/versions/0004_sentinela.py` — migration
- `tests/test_sentinela.py` — 24 testes

**Rotas** (`/api/v1/sentinela/`):

| Rota | Autenticação | Função |
|---|---|---|
| `POST /eventos` | token de ingestão + só loopback | extensão e app enviam observações em lote (até 200) |
| `GET /eventos` | login | lista com filtros (bloqueadas, dispositivo, data, paginação) |
| `GET /resumo` | login | totais, temas mais barrados, série diária, dispositivos |
| `GET/PATCH /config` | login | ativo, sensibilidade, retenção |
| `POST /config/pin` · `/pin/verificar` | login | define/troca/verifica PIN |
| `POST /token/rotacionar` | login | gera novo token de ingestão |
| `POST /importar` | login | importa o `supervisao.jsonl` legado |

**Decisões e o porquê:**

- **Duas credenciais diferentes de propósito.** A extensão não tem como carregar
  um JWT de usuário; por isso a ingestão usa um token próprio. E uma rota aberta
  deixaria qualquer processo local forjar ou poluir o registro parental — então
  ela exige token **e** origem loopback.
- **Sem `workspace_id`.** O registro de supervisão pertence à máquina/família,
  não a um espaço de trabalho comercial. Amarrá-lo a um workspace do CRM seria
  errado conceitualmente e estranho na prática.
- **Texto da busca cifrado em repouso** (Fernet, o mesmo que o CRM já usava para
  tokens). É o que uma criança digitou: material sensível.
- **PIN errado vira evento de supervisão.** O responsável vê quem tentou
  desarmar a proteção.
- **Trocar o PIN exige o PIN atual.** Senão bastaria pegar a sessão aberta do
  responsável para desarmar a trava.
- **`/importar` foi mantido.** O caminho antigo do `.jsonl` continua existindo:
  nada do que já existia se perdeu.

### 3.4 Fim do exportar/importar a mão

Antes: o responsável clicava "Exportar" no popup, salvava um `.jsonl` e
importava manualmente no app PowerShell. Agora a entrega é automática, por dois
caminhos:

**Extensão** — `apps/guardian/app/extensao/sync.js` (novo):
- fila **offline-first** no `chrome.storage`: o log local continua sendo a
  verdade, o envio é espelho;
- envio em lotes; se o painel estiver desligado ou o token falhar, a fila fica
  **intacta** (repetir um evento é melhor que perder um);
- recusa qualquer endereço que não seja loopback;
- quem fala com `127.0.0.1` é o service worker (único com `host_permissions`);
  o content script só avisa, e falha de envio **nunca** atrapalha o bloqueio;
- popup ganhou a aba **Painel**: estado da conexão, token, nome do dispositivo,
  "sincronizar agora". O campo do token é limpo depois de salvar.

**App Windows** — `Sentinela-Ponte.ps1` e `Conectar-Painel.ps1` (novos):
- `Add-SupervisaoRegistro` espelha no painel em *best-effort* — painel fora do ar
  não pode parar a proteção, e o `.jsonl` já guardou o registro;
- `Sync-SupervisaoComPainel` envia o histórico acumulado;
- `Conectar-Painel.ps1 -Token <token>` conecta; tem `-Status`, `-Desligar`,
  `-EnviarTudo`, `-Simular`.

### 3.5 Painel do responsável dentro da SPA

Página **Sentinela** na navegação principal (atalho `g s`), construída com os
mesmos primitivos do CRM (`.card`, `.kpi`, `.btn-ghost`) — as duas metades da
suite parecem o mesmo produto:

- indicadores: bloqueadas, observadas, dispositivos, último sinal;
- lista de tentativas com o veredito da IA (tema + confiança), filtro "só
  bloqueadas", paginação;
- temas mais barrados com barra proporcional;
- proteção: ativo, sensibilidade, retenção, PIN — **salva ao mudar**, sem botão
  "Salvar" para esquecer de clicar;
- **Conectar dispositivo**: mostra o token só sob clique (é credencial) e permite
  gerar outro, avisando que os dispositivos antigos param até serem reconectados.

### 3.6 A casca virou o Sentinela (não mais o CRM com uma página a mais)

Até aqui o app já era **um só** — um servidor, uma SPA, um login, um design
system. Mas ele ainda **se apresentava** como VisiQuost: título, logo do menu e,
principalmente, a tela de entrada, que vendia só o CRM. O Sentinela tinha virado
uma página dentro do app do CRM, quando o certo é o inverso.

O que mudou:

- **Identidade** — título da página, marca do menu lateral, marca da tela de
  entrada e título da API passaram a ser **Sentinela**. `VisiQuost` continua
  sendo o nome do **módulo de CRM** (e da pasta de trabalho em disco, que é um
  caminho real e não podia mudar sem quebrar quem já usa).
- **Tela de entrada** — a manchete deixou de ser "Seu CRM. Sua máquina. Zero
  cloud." e virou "**Sua família protegida. Seu trabalho organizado. Zero
  nuvem.**" Os quatro cartões passaram a ser dois do Sentinela (filtro que não
  desliga, painel do responsável) e dois do CRM (Jarvis local, CRM completo) —
  nenhuma promessa do texto antigo foi perdida, só reorganizada. Tudo traduzido
  PT/EN.
- **Menu** — Sentinela é o **primeiro item**, e os itens do CRM ficam abaixo de
  um rótulo de seção **CRM**. A leitura vira "este app é o Sentinela, e o CRM é
  uma parte dele".
- **Onde o app abre** — na primeira execução, no Sentinela (é a cara do
  produto). Depois disso ele **lembra a última seção usada**, guardada em
  `localStorage`. Forçar sempre uma das duas metades irritaria a outra: quem usa
  o CRM todo dia continua caindo no CRM.
- Contador de testes da tela de entrada corrigido de 434 para **642**
  (139 + 458 + 25 + 20, conferidos).

### 3.7 Limpeza e consolidação

- `INICIAR.bat` / `INSTALAR.bat` na raiz — um ponto de entrada. O instalador
  **delega** ao do CRM em vez de duplicar a detecção de Python.
- Removidos **1,8 MB** de despejos de código que já nasciam desatualizados
  (`TUDO_PARA_FABLE.md`, `PROJECT_SOURCE_DUMP.md`,
  `SENTINELA-INTEIRO-PARA-FABLE.txt`). O código está no repositório; o histórico
  guarda os despejos se alguém precisar.
- `objetivos crm/` → `apps/crm/docs/objetivos/` (pasta com espaço no nome era
  papercut no monorepo), com as referências internas atualizadas.
- **Documentação que prometia o que não existe:** README, ARCHITECTURE e ROADMAP
  do CRM ainda descreviam escalonamento para a API da Anthropic com
  `ANTHROPIC_API_KEY`. Verifiquei o código: esse caminho não existe (a config
  `anthropic_*` foi removida há tempo) e a promessa contradizia a regra de zero
  APIs externas. Removida.
- `CONTINUAR-AQUI.md` atualizado: caminhos do monorepo, novas suítes, e a regra
  antiga "não escrever na pasta da CRM" removida — agora é o mesmo projeto.

---

## 4. Validação

Tudo abaixo foi executado de verdade, na última rodada, com o código final.

| Suíte | Resultado | O que cobre |
|---|---|---|
| Classificador (PowerShell) | **139 / 139** | texto PT/EN/ES/FR, evasões, contexto seguro |
| Corpus de precisão | **373 / 373 · 100%** | 0 falso-positivo, 0 falso-negativo |
| API + CRM (pytest) | **458 passed** | rotas, serviços, Jarvis, módulo Sentinela (24 novos) |
| E2E extensão + ponte PS | **25 / 25** | navegador real → API; ponte PowerShell |
| E2E painel na SPA | **30 / 30** | identidade da casca, página Sentinela, tema claro, celular, i18n |
| Migrations | up / down / up | em banco limpo |
| Demo do pitch | 4 / 4 | sem erro de JS |

**Os E2E não são simulação.** `Testar-Sync.py` sobe um servidor num banco
temporário, carrega a **extensão real** no Chromium, faz uma busca imprópria numa
página servida por esse servidor e verifica que:

1. a IA local bloqueou a busca;
2. o evento chegou **sozinho** ao painel (sem forçar sincronização);
3. o veredito da IA veio junto;
4. a busca está **cifrada** no banco;
5. com token errado a ingestão é recusada e **a fila não se perde**;
6. a ponte PowerShell recusa endereço fora do loopback e fica silenciosa quando
   desligada.

`Testar-Painel.py` semeia eventos pela API, entra no app pelo navegador e confere
a identidade da casca (título, marca, manchete, Sentinela como primeiro item do
menu, rótulo da seção CRM, onde o app abre e se ele lembra a última seção), os
números do painel, o filtro, a persistência da configuração, o modal do token, o
tema claro, a tradução PT/EN da entrada, a ausência de rolagem horizontal no
celular e **zero erro de console**.

---

## 5. Bugs encontrados e corrigidos

| Bug | Onde | Consequência |
|---|---|---|
| Credencial demo inexistente (`demo@example.com`) | `scripts/ui_snapshot.py` | script de screenshots quebrado desde antes da sessão |
| `openModal` não restaurava o rótulo do botão Salvar | `frontend/assets/app.js` | fechar com Esc deixava "Gerar novo token" no modal seguinte |
| `select()` de coluna única devolve escalares, não tuplas | `sentinela_service.resumo()` | `/resumo` estourava (pego pelo teste novo) |
| Precedência de `\|\|` sobre `+` na contagem de descartados | `extensao/sync.js` | contador de eventos descartados errado |
| Histórico invisível para `git log <arquivo>` | merge do monorepo | refeito com reescrita de prefixo |

---

## 6. Segurança e privacidade

- Classificação acontece **no dispositivo**; nada sai da máquina.
- Texto das buscas **cifrado em repouso** (Fernet).
- Ingestão exige **token válido** *e* **origem loopback**.
- **Limite de taxa** na única rota alcançável sem login (`/sentinela/eventos`):
  burst de 60 cobre o envio do histórico e trava enxurrada de um processo local.
- PIN com hash (argon2, o mesmo do CRM); trocar exige o PIN atual; tentativa
  errada vira evento.
- Token de ingestão rotacionável; só aparece sob clique explícito.
- Retenção configurável (padrão 90 dias) aplicada a cada ingestão.
- Varredura de segredos antes de publicar: nenhum `.env`, banco ou chave
  versionado — só os `.env.example` com placeholders.

---

## 7. Números

- **99 commits** — 89 preservados dos dois repos + 10 da unificação
- **45 arquivos alterados** sobre a base: **+2.888 / −44.501 linhas**
- **15 arquivos novos**, 3 removidos, 10 renomeados
- **79 verificações automatizadas novas** (24 pytest + 25 E2E + 30 E2E)

**Arquivos novos:**

```
INICIAR.bat · INSTALAR.bat · .gitignore
packages/ui/sentinela-tokens.css · packages/ui/README.md
apps/crm/backend/app/models/sentinela.py
apps/crm/backend/app/services/sentinela_service.py
apps/crm/backend/app/api/routes_sentinela.py
apps/crm/backend/alembic/versions/0004_sentinela.py
apps/crm/backend/tests/test_sentinela.py
apps/guardian/app/Sentinela-Ponte.ps1
apps/guardian/app/Conectar-Painel.ps1
apps/guardian/app/extensao/sync.js
apps/guardian/app/Testes/Testar-Sync.py
apps/guardian/app/Testes/Testar-Painel.py
```

---

## 8. Limitações conhecidas (nenhuma bloqueante)

1. **Fontes.** Sora e DM Sans só aparecem se instaladas no sistema; offline a
   pilha cai para Segoe UI. Baixá-las exigiria requisição externa, proibida.
2. **A demo do pitch mantém a paleta inline** em vez de importar o pacote,
   porque precisa ser um arquivo único. Duplicação intencional, documentada em
   `packages/ui/README.md` — ao mudar um token, conferir se a demo acompanha.
3. **Dados do Sentinela não são workspace-scoped.** Correto para instalação de
   família (quem loga no `127.0.0.1` é o responsável); errado se o CRM um dia
   servir usuários não relacionados na mesma instalação.
4. **`/resumo` monta a série diária em Python**, carregando até 5.000 eventos.
   Suficiente para 90 dias de retenção; janelas maiores pedem agregação em SQL.
5. **Retenção apaga em definitivo.** `retencao_dias = 0` guarda para sempre.
6. **Venv copiada:** os `.exe` em `Scripts/` ainda embutem o caminho da pasta
   antiga. Todos os comandos documentados usam `python.exe -m ...`, que funciona;
   `INSTALAR.bat` recria a venv limpa numa máquina nova.
7. **Sem CI.** O `ci.yml` do CRM estava no `.gitignore` do repo de origem, então
   nunca esteve versionado e não veio na união.
8. **Limites do heurístico de imagem** seguem os de antes (superfícies lisas cor
   de pele podem ser borradas) — não foi mexido nessa parte.

---

## 9. Recomendações para a próxima etapa

1. **CI na raiz** (`.github/workflows/`) rodando as cinco suítes em cada push —
   é o que falta para o monorepo se defender sozinho.
2. **Conectar dispositivo sem copiar token à mão:** o instalador do Sentinela
   poderia ler o token do painel e injetá-lo na política gerenciada da extensão.
3. **Jarvis entender o painel:** o motor de intents é local e extensível; dá para
   responder "o que meu filho pesquisou hoje?" reutilizando o `sentinela_service`.
4. **Agregação em SQL no `/resumo`** quando a retenção passar de alguns meses.
5. **Modelo treinado para imagem** no slot que já existe
   (`apps/guardian/app/extensao/modelo/`) — é a única forma de resolver os falsos
   positivos de superfície lisa.
6. **Decidir a visibilidade do repositório.** Foi publicado como **privado** por
   ser a escolha reversível. Um comando torna público:
   `gh repo edit percihenriques-byte/sentinela-suite --visibility public`.

---

## 10. Como rodar

```bat
INSTALAR.bat                        :: 1x - Python, dependencias, banco, dados demo
INICIAR.bat                         :: http://127.0.0.1:8000/
apps\guardian\app\INSTALAR.bat      :: protecao do PC (pede administrador 1x)
```

Ligar a proteção ao painel — o token sai de **Sentinela → Conectar dispositivo**:

```powershell
apps\guardian\app\Conectar-Painel.ps1 -Token <token>
```

Na extensão do navegador, o mesmo token vai na aba **Painel**.

**Testes:**

```bat
powershell -File apps\guardian\app\Testes\Executar-Testes.ps1
powershell -File apps\guardian\app\Testes\Medir-Precisao.ps1
cd apps\crm\backend && .venv\Scripts\python.exe -m pytest -q
apps\crm\backend\.venv\Scripts\python.exe apps\guardian\app\Testes\Testar-Sync.py
apps\crm\backend\.venv\Scripts\python.exe apps\guardian\app\Testes\Testar-Painel.py
```

Os repositórios de origem (`sentinela` e `visiquost-crm`) continuam intactos no
GitHub — nada foi apagado neles.

---

## 11. Auditoria independente e correcoes

Uma auditoria externa leu o codigo (nao este relatorio) e listou 12 achados,
tres deles bloqueando release. Confirmei cada um contra o codigo antes de mexer
— inclusive reproduzindo o A1 — e todos foram corrigidos, com teste que trava a
regressao (`apps/crm/backend/tests/test_auditoria.py`, 20 testes).

| # | Achado | O que estava errado | Correcao |
|---|---|---|---|
| A1 | Chave de cifra ausente | O instalador gerava `APP_SECRET_KEY` e esquecia `FIELD_ENCRYPTION_KEY`. Em instalacao limpa a chave ficava vazia, `encrypt()` levantava `RuntimeError` e a **primeira busca da crianca virava 500** — o painel nunca recebia evento. O E2E nao pegava porque o ambiente de teste define a chave. | Instalador gera a chave (e preenche instalacao antiga que esteja sem ela). O app **recusa subir** sem ela, com mensagem dizendo como gerar. |
| A2 | Bind em `0.0.0.0` | Os quatro pontos de inicializacao abriam o servidor para a rede "para o celular acessar". O painel — com o historico decifrado — ficava alcancavel por qualquer aparelho da Wi-Fi, protegido so por login. | `127.0.0.1` por padrao. LAN so com `SENTINELA_BIND_LAN=1`. |
| A3 | Conta demo fixa | `demo@visiquost.app` / `demo1234` criada em toda instalacao. Com A2, credencial publica para o historico de uma crianca. | Bootstrap so com `APP_ENV=dev`; `.env.example` instala como `prod`; a SPA detecta instalacao nova, abre em "Criar conta" e some com o botao de demo. O painel pede o PIN na primeira visita. |
| A4/A5 | Config contradizendo o produto | `.env.example` anunciava `ANTHROPIC_*`; default de CORS apontava para `localhost:3000`, origem que nao existe. | Ambos para loopback:8000; teste garante que o default nunca inclui origem nao-loopback. |
| A6 | PIN sem lockout | 10.000 combinacoes caindo em segundos. Registrar a tentativa foi confundido com defesa contra a tentativa. | Lockout progressivo persistido (5 → 1 min, 10 → 15 min, 15 → 1 h), valendo tambem na troca de PIN, mais balde de taxa na rota. |
| A7 | Sem CI | As cinco suites so rodavam a mao. | `.github/workflows/ci.yml`: pytest, ciclo de migrations e classificador+corpus em todo push; E2E sob `workflow_dispatch`. |
| A8 | `/resumo` com teto de 5000 | A serie diaria contava em Python ate 5000 eventos enquanto os cartoes usavam `COUNT`: passando do teto, grafico e cartoes discordavam **em silencio**. | Agregacao em SQL (`func.date`) com fallback; teste com 5.200 eventos confirma que serie e totais batem. |
| A9 | Cores fora dos tokens | `#fb923c` e `#f472b6` cravados. | Viraram tokens; `app.css` agora so tem `#000` e `#fff`, com teste que trava isso. |
| A10 | Painel sem escopo | Decisao correta, mas sem nada impedindo a evolucao perigosa. | Invariante registrado no proprio modulo, dizendo o que fazer quando multiusuario entrar. |
| A11 | Retencao so na ingestao | Instalacao ociosa nunca purgava — dado sensivel ficava indefinidamente. | Laco proprio no lifespan, que roda sempre (o de backup e opcional e retornava cedo). |
| A12 | Duas validacoes para os mesmos dados | Import legado e ingestao ao vivo divergiam. | `normalizar_evento()` unica, consumida pelas duas portas. |

Um achado do auditor precisa de ressalva: ele descreveu A1 como "chave vazia →
`RuntimeError`", e esta certo — mas vale registrar que o outro `.env.example`
(`apps/crm/.env.example`, nao usado pelo instalador) trazia um **placeholder
fixo**. Se o instalador copiasse aquele, nao haveria erro nenhum: toda
instalacao compartilharia a mesma chave conhecida, e a "cifra em repouso" seria
teatro. Os dois arquivos foram corrigidos.

O que a auditoria confirmou como correto (verificado no codigo, nao assumido):
fonte unica de classificacao respeitada, token de ingestao com comparacao em
tempo constante, cifra em repouso real, troca de PIN exigindo o atual,
migrations aditivas e ordem correta do middleware.

**Estado apos as correcoes:** 478 pytest · 32/32 E2E painel · 25/25 E2E extensao
· 139/139 classificador · corpus 373/373 · migrations up/down/up.


---

## 12. Segunda auditoria independente (rodada do zero)

O auditor refez a auditoria a partir do codigo limpo, sem partir da lista
anterior — e o metodo se pagou: dois achados novos so apareceram porque ele
contou termos e leu o middleware em vez de reconferir o que ja estava fechado.
Veredito dele: **liberado para release**, com um P1 recomendado antes de
distribuir. Confirmei os seis achados no codigo antes de mexer.

| # | Achado | O que estava errado | Correcao |
|---|---|---|---|
| B2 | Classificadores divergentes | O relatorio afirmava "fonte unica espelhada em JS". Contando: **315 termos no PS, 313 no JS**. Faltavam `xingamentos pesados` e `como criar conta no` **no lado que protege o navegador da crianca** — e o corpus marcava 100% sem perceber, porque roda contra o PS. | Termos reconciliados (315 = 315). Seis testes de paridade comparam categoria a categoria, termo a termo, peso a peso, mais o contexto seguro. Novo `Testar-Paridade.py` roda o corpus **contra o motor JS** num Chromium real: **369/369, 100%**. Os dois arquivos agora avisam no cabecalho que sao espelho. |
| B1 | Rate limit por `X-Forwarded-For` | O balde era chaveado por um header **escrito pelo cliente**. Num app loopback-only nao ha proxy: um script local mandava um IP diferente a cada request, ganhava balde novo e anulava o teto de ingestao e o limite da rota de PIN. | So confia no header com `TRUST_PROXY=1`; por padrao usa o peer real da conexao. Teste prova que 20 requests com XFF variavel nao multiplicam o balde. |
| B3 | Segredo de assinatura sem fail-fast | A chave de cifra ganhou guarda de startup; o segredo que **assina o JWT** nao. Instalador que falhasse em silencio subiria assinando com um segredo publico, e qualquer um forjaria sessao. | Mesma guarda: em `APP_ENV != dev`, secret vazio ou default recusa subir, dizendo como gerar. `dev` segue sem atrito. |
| B4 | CI ausente do repositorio | Correto: no commit auditado o CI nao existia. | Ja estava commitado localmente; o que faltava era publicar (ver abaixo). Removi tambem a linha `.github/workflows/` de `apps/crm/.gitignore` — resquicio de quando o CRM era repo proprio — e um teste agora falha se ela voltar. |
| B5 | Retencao zero sem aviso | `retencao_dias = 0` guarda para sempre, em silencio. Sao buscas cifradas de uma crianca acumulando sem prazo. | A tela avisa em ambar: "guardando para sempre — a purga automatica esta desligada". |
| B6 | Painel sem escopo de workspace | Seguro hoje (instalacao de familia), fragil se virar multiusuario. | Segue como divida consciente; o invariante ja esta escrito no proprio modulo, dizendo o que fazer no dia em que multiusuario entrar. |

**Uma correcao ao diagnostico do B4:** o auditor atribuiu o CI ausente a linha
61 de `apps/crm/.gitignore`. Nao era a causa — o arquivo esta na **raiz**, fora
do alcance daquele ignore, e `git check-ignore` confirma que nao era ignorado.
A causa real: o GitHub recusa arquivos em `.github/workflows/` vindos de um
token OAuth sem o escopo `workflow`, entao o commit ficou local. A linha do
`.gitignore` era mesmo lixo e foi removida, mas por outro motivo.

**Estado apos esta rodada:** 492 pytest · 369/369 corpus no motor JS · 373/373
corpus no motor PS · 139/139 classificador · 32/32 E2E painel · 25/25 E2E
extensao.
