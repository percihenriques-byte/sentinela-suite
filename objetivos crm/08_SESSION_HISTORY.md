# Histórico de sessões

Timeline resumida das principais rodadas de trabalho autônomo. Detalhes completos em
`Desktop/chat claude da crm/SESSION_STATE.md`.

## Sessão 1 — Bootstrap inicial (2026-07-11)
- Setup FastAPI + SQLModel + SQLite
- Auth JWT com argon2
- Modelos base: User, Workspace, Contact, Company, Opportunity, Lead, Pipeline, Stage, Task, Meeting
- CRUD routes básicos
- Frontend HTML+CSS+JS single-page

## Sessão 2 — Jarvis intent engine (2026-07-12)
- `local_engine.py` com 40+ intents PT/EN
- Regex + fuzzy matching (difflib)
- IntentResult + IntentHandler pattern
- Detecção de idioma
- Conversation persistence (JarvisConversation + JarvisMessage)

## Sessão 3 — Loop de 8h "polish contínuo" (2026-07-12/13)
Sessão longa com ticks 54–129. Cobriu:
- Empty states polidos nos 3 sub-cards do dashboard
- Jarvis panel colapsável (desktop)
- Kanban scroll hint + colunas colapsáveis
- Signature widget: on-device footprint
- Frontend design pass (skill `frontend-design`)
- CSS custom properties (dark/light theme)
- 100+ tests em `test_visiquost_v1_intents.py`
- Fixes: PT lang detection expandido, undo of undo blocked, tests flakiness

## Sessão 4 — Loop 4h "improve CRM" (2026-07-15)
Ticks 130-140. Cobriu:
- **Tick 130** — top-of-page progress bar durante API calls
- **Tick 131** — NEW badge em entidades < 24h (fix UTC parsing)
- **Tick 132** — meetings agrupadas por dia (Hoje/Amanhã/Semana/Depois)
- **Tick 133** — ↑↓ + Enter row navigation em tabelas
- **Tick 134** — tasks page reescrita (buckets, priority icons, click-to-complete)
- **Tick 135** — activity feed traduzido + ícones coloridos por severidade
- **Tick 136** — kanban keyboard reorder (WAI-ARIA aria-grabbed)
- **Tick 137** — bulk toolbar polida (pill count + danger btn) + bulk CSV export
- **Tick 138** — drawer sticky header + focus restore + role="dialog"
- **Tick 139** — kanban drop indicator (dashed placeholder)
- **Tick 140** — modal Enter submete (hidden submit btn) + focus restore

## Sessão 5 — GitHub + fixes reais reportados (2026-07-15/16)
Depois de vários bugs reais reportados pelo Perci:
- Criou repo privado no GitHub (`gh auth login` via device code)
- Fix INSTALAR.bat: 3 bugs de parser CMD (`"py -3"` entre aspas, `for /f %%d.%%d`,
  `echo (nao critico)` fechando if-block)
- Fix INICIAR.bat: browser abria antes de uvicorn subir → poll healthz
- Refactor pra desktop app (pywebview) → Perci não queria → reverteu pra terminal só
- Refactor auth landing (Perci: "está horrivel") → hero gigante gradient + feature cards + stats
- Fix demo login: `demo@visiquost.local` → `demo@visiquost.app` (pydantic rejeita `.local`)
- Fix body overflow:hidden global travando scroll da landing
- Fix cache do browser (no-store headers pra assets)

## Sessão 6 — Walkthroughs iterativos (2026-07-16)
5 rounds de Playwright walkthrough como usuário real (slow_mo 60-120ms):

- **Round 1 (full_flow.py)** — 18/18 checks E2E
- **Round 2 (brutal_walkthrough.py)** — Cmd-K, drawer, bulk, kanban, mobile
  - Bug: Jarvis "briefing" em EN mesmo com locale PT → default lang = PT
  - Bug: "top oportunidades" (sem número) → regex `\d*`
  - Bug: CSV export batia limit=1000 → `fetchAllPages()` com pagination real
  - Bug: greeting perdia palavra "local" ("locais" ≠ "local") → texto ajustado
  - Bug: drawer header "Contact" em PT → DRAWER_LABELS_PT
  - Bug: stages "Prospecting" em EN → localizeStage()
  - Bug: "808.0  KB" whitespace duplo → span reorg
  - Bug: Enter no modal → hidden submit button
- **Round 3 (deeper_walk.py)** — task filters, WIP, kbd nav, i18n switch
  - Bug: hero h1 hardcoded PT → data-i18n em cada elemento
- **Round 4 (r4_walk.py)** — automations, scoring, undo, prefs, theme
  - Bug: undo desfazia só update, não create → estendeu handler para create → soft-delete
- **Round 5 (r5_edge.py)** — email dup, unicode, XSS, rapid nav, Ctrl+/, msg gigante
  - 0 issues genuínos

**Estado final**: 434/434 backend · 4 walkthroughs suites · 0 friction · 0 JS errors · 0 HTTP 4xx/5xx.

## Métricas totais

- **Commits nesta sessão total**: ~15 (após criação do repo)
- **Linhas de código**:
  - `backend/app/jarvis/local_engine.py`: ~5500
  - `frontend/assets/app.js`: ~5000
  - `frontend/assets/app.css`: ~1500
  - `backend/app/models/`: ~700
  - `backend/tests/`: ~3000
- **Intents Jarvis**: 80+
- **Tests pytest**: 434
- **Cobertura**: alto (todos os endpoints REST + todos os intents críticos)
