# Arquitetura

## Stack

### Backend
- **Python 3.11** (roda em 3.10+)
- **FastAPI** — async web framework
- **SQLModel** — ORM (Pydantic + SQLAlchemy)
- **SQLite** (dev/prod) — arquivo `backend/jarvis_crm.db`. Portable, sem servidor.
- **Alembic** — migrations
- **argon2-cffi** — password hashing
- **PyJWT** — JWT access + refresh tokens
- **cryptography (Fernet)** — encryption em campos sensíveis
- **pywebview>=5.0** — (opcional) launcher desktop com WebView2 nativo Windows
- **uvicorn** — ASGI server

### Frontend
- **Vanilla JS** — ~5000 linhas, zero dependências CDN, zero build step
- **Vanilla CSS** — sem framework, custom properties (dark/light theme)
- **SVG** inline pra ícones (nenhum icon library externo)
- **Playwright** (dev only) — walkthrough testing "as user"

### Sem/Removido
- ❌ Nenhuma Google Fonts / CDN (system font stack)
- ❌ Nenhum OAuth, Google/LinkedIn/Anthropic API
- ❌ Nenhum bundler (webpack/vite/esbuild) — HTML/CSS/JS servido direto
- ❌ Nenhum front-end framework (React/Vue/Svelte)
- ❌ Nenhum cloud LLM em runtime (Jarvis é 100% local)

## Camadas do backend

```
backend/app/
├── main.py               — FastAPI app factory + static mount + no-cache
├── core/
│   ├── config.py         — settings via pydantic-settings
│   ├── security.py       — JWT create/verify, password hash
│   ├── crypto.py         — Fernet encrypt/decrypt
│   ├── logging.py        — structured JSON logging + request UUIDs
│   └── middleware.py     — request logging, CORS
├── db/session.py         — SQLModel engine + get_session dep
├── models/               — SQLModel tables (identity, work, pipeline, tags, ...)
├── schemas/              — Pydantic request/response models
├── services/             — business logic (jarvis_service, crud, workflow_service, ...)
├── api/                  — FastAPI routers (routes_contacts.py, routes_jarvis.py, ...)
└── jarvis/
    ├── local_engine.py   — ~5500 linhas: 80+ intents + regex + fuzzy + handlers
    ├── context.py        — WorkspaceSnapshot builder (KPIs, preferences)
    ├── tools.py          — ToolContext (session, workspace_id, prefs)
    ├── date_parser.py    — "amanhã 15h", "próxima segunda 3pm"
    ├── device_tools.py   — read file (sandboxed to workdir), scan work dir
    └── planner.py        — Manus-like plan→execute→report
```

## Camadas do frontend

```
frontend/
├── index.html            — single page (auth-view + app-view + modals + drawer)
├── assets/
│   ├── app.js            — todo o JS num arquivo (~5000 linhas)
│   └── app.css           — todo o CSS num arquivo (~1500 linhas)
```

O JS não é modularizado (sem `import/export`) — funções top-level, escopo global mínimo,
`state` object para runtime. Rotas internas via `nav button[data-page]` + `show(view)`.

## Fluxo típico de request

```
Browser
  └─ POST /api/v1/jarvis/chat  {message, conversation_id?}
       └─ FastAPI middleware (assigns req_id UUID)
            └─ auth deps (get_current_user via JWT)
                 └─ routes_jarvis.chat()
                      └─ jarvis_service.process_message(message, user, session)
                           ├─ WorkspaceSnapshot.build(session, workspace_id)  — KPIs, preferences
                           ├─ local_engine.route_intent(text, snap, ctx)
                           │    ├─ _detect_lang(text) → pt/en
                           │    ├─ pattern matching (regex + fuzzy)
                           │    ├─ intent handler (create_contact, top_opportunities, ...)
                           │    └─ IntentResult(reply, tool_calls, intent, confidence)
                           ├─ [se needs_llm] cloud escalation (só se ANTHROPIC_API_KEY setado
                           │                   — atualmente DESLIGADO por hard rule)
                           └─ persist message + assistant reply em JarvisMessage
       └─ Response {reply, intent, conversation_id, tool_calls}
```

## Modelo de dados (principais)

```
Workspace (multi-tenant boundary)
  ├─ User (owner + members)
  ├─ Contact
  ├─ Company
  ├─ Opportunity  → Pipeline → Stage
  ├─ Lead        → LeadScoringRule (auto-recompute)
  ├─ Task
  ├─ Meeting
  ├─ Note (polymorphic: related_contact_id | related_company_id | ...)
  ├─ Activity (append-only feed, kind + subject_type + subject_id)
  ├─ Tag + TagLink (M2M polymorphic)
  ├─ Workflow (triggers + actions)
  │   └─ WorkflowRun (audit trail)
  ├─ JarvisConversation
  │   └─ JarvisMessage (role, content, tool_calls, intent, conversation_context)
  └─ JarvisMemory (preferences kv: tone, preferred_name, language)
```

`workspace_id` em toda tabela + `deleted_at` para soft delete + índices compostos nos hot paths
(`(workspace_id, created_at)`, `(workspace_id, deleted_at)`).

## Deploy local

```
INICIAR.bat
  ├─ Detecta backend\.venv\Scripts\python.exe
  ├─ Se não existe → chama INSTALAR.bat (bootstrap completo)
  ├─ Detecta IP LAN via `ipconfig | findstr IPv4.*192.\|10.\|172.`
  ├─ Mostra caixa com URLs (PC + celular)
  └─ Roda uvicorn no PROPRIO terminal (bloqueante) em 0.0.0.0:8000
```

Uvicorn em 0.0.0.0 permite celular na mesma Wi-Fi acessar via IP local.

## Regras arquiteturais fortes

- **`workspace_id` em toda query** — nunca `.filter(Model.id == x)` sem filtrar workspace
- **Soft delete** — `deleted_at IS NULL` em todo listing default
- **UUIDs** — todas PKs são UUID4 (não int) → import/export sem ID collision
- **Timestamps UTC** — `datetime.now(timezone.utc)` sempre, sem tz naive
- **Pydantic v2 validators** — validação em request schema, não em service
- **Static no-cache** — HTML/JS/CSS servido com `Cache-Control: no-cache` (evita user preso
  em versão velha após deploy)
