# 🛡️ Sentinela Suite

**Um app só**, com a UX do Sentinela: um servidor, uma janela, um login, um
instalador. Dentro dele, dois módulos:

| Módulo | O que faz |
|---|---|
| **Sentinela** (`apps/guardian`) | Controle parental à prova de incógnito: filtro de rede (DNS + hosts + política do navegador), IA local que analisa busca, texto e imagem, trava por PIN e registro de supervisão. É a cara do app: a marca, a paleta e a primeira seção do menu. |
| **VisiQuost** (`apps/crm`) | O CRM, uma seção dentro do mesmo app: contatos, empresas, oportunidades, pipeline kanban, tarefas, reuniões, lead scoring, automações e o assistente **Jarvis**. |

Na primeira vez o app abre no Sentinela. Depois disso ele lembra a última seção
usada — quem passa o dia no CRM continua caindo no CRM.

**Zero APIs externas.** Nada é enviado para a internet — nem busca, nem dado de
cliente, nem telemetria. Os dois módulos falam entre si só por `127.0.0.1`.

---

## Começar

```bat
INSTALAR.bat      :: 1x — instala Python, dependências, banco e dados demo
INICIAR.bat       :: sobe o servidor local em http://127.0.0.1:8000/
```

Para proteger o PC da família (pede administrador uma vez):

```bat
apps\guardian\app\INSTALAR.bat
```

Para ligar a proteção ao painel:

```powershell
apps\guardian\app\Conectar-Painel.ps1 -Token <token do painel>
```

O token sai do próprio painel, em **Sentinela → Conectar dispositivo**.
Na extensão do navegador, o mesmo token vai na aba **Painel**.

---

## Como as peças se encaixam

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
              │  /api/v1/... (CRM)        │
              └────────────┬──────────────┘
                           ▼
              ┌───────────────────────────┐
              │  SPA unica                │
              │  Painel do responsavel    │
              │  + CRM, mesma UX          │
              └───────────────────────────┘
```

O classificador tem **uma** fonte de verdade
(`apps/guardian/app/Sentinela-Classificador.ps1`), espelhada em JS na extensão
(`classificador.js`). O servidor **não** classifica: ele guarda o veredito de
quem observou, para não existir uma terceira cópia da mesma regra.

---

## Mapa do repositório

```
apps/
  guardian/          Sentinela — app Windows (PowerShell) + extensao MV3 + demo
    app/             scripts, extensao/, gui/, Testes/
    demo/            pagina de pitch (auto-contida)
    docs/
  crm/               VisiQuost — FastAPI + SQLModel + SPA
    backend/         app/, alembic/, tests/, scripts/
    frontend/        index.html + assets/
    docs/
packages/
  ui/                design system Sentinela — fonte unica dos tokens
```

## Testes

| Suite | Comando | Cobre |
|---|---|---|
| Classificador (139) | `powershell -File apps\guardian\app\Testes\Executar-Testes.ps1` | texto PT/EN/ES/FR, evasões, contexto seguro |
| Precisão (corpus 373) | `powershell -File apps\guardian\app\Testes\Medir-Precisao.ps1` | acurácia, falsos positivos/negativos |
| API + CRM (492) | `apps\crm\backend\.venv\Scripts\python.exe -m pytest -q` (em `apps/crm/backend`) | rotas, serviços, Jarvis, módulo Sentinela |
| E2E extensão + ponte (25) | `apps\crm\backend\.venv\Scripts\python.exe apps\guardian\app\Testes\Testar-Sync.py` | navegador real → API, ponte PowerShell |
| E2E painel (32) | `apps\crm\backend\.venv\Scripts\python.exe apps\guardian\app\Testes\Testar-Painel.py` | identidade da casca, página Sentinela, tema claro, celular |

## Documentação

- [`RELATORIO-UNIFICACAO.md`](RELATORIO-UNIFICACAO.md) — como os dois projetos viraram um: decisões, validação e limitações

- [`packages/ui/README.md`](packages/ui/README.md) — design system e como trocar a identidade em um lugar só
- [`apps/guardian/README.md`](apps/guardian/README.md) — o Sentinela em detalhe
- [`apps/guardian/CONTINUAR-AQUI.md`](apps/guardian/CONTINUAR-AQUI.md) — estado do projeto e regras de trabalho
- [`apps/crm/README.md`](apps/crm/README.md) — o CRM em detalhe
- [`apps/crm/docs/ARCHITECTURE.md`](apps/crm/docs/ARCHITECTURE.md) — arquitetura do backend

## Histórico

Os dois repositórios foram unidos preservando o histórico completo, com os
caminhos já reescritos para o layout do monorepo. Ou seja: `git log` e
`git blame` num arquivo mostram a vida inteira dele, inclusive antes da união.

```bash
git log --oneline -- apps/guardian/app/Sentinela-Classificador.ps1
git log --oneline -- apps/crm/backend/app/main.py
```

## Privacidade e rede

- O servidor escuta **só em `127.0.0.1`**. Abrir para a rede local exige
  `SENTINELA_BIND_LAN=1` — opt-in consciente, porque o painel guarda o histórico
  de navegação de uma criança e "rede local" costuma incluir estranhos.
- **Não existe conta padrão.** O responsável cria a dele no primeiro acesso e
  define o PIN ali mesmo. A conta demo só existe com `APP_ENV=dev`.
- Buscas e páginas são classificadas **no dispositivo**; nada é enviado para fora.
- O texto das buscas fica **cifrado em repouso** (Fernet) no banco local.
- O registro de supervisão tem janela de retenção configurável (padrão 90 dias).
- Ingestão só aceita conexão de `127.0.0.1` **e** token válido.
- PIN com lockout progressivo (5 erros → 1 min, 10 → 15 min, 15 → 1 h): um PIN de
  4 dígitos sem trava cai em segundos.
