# VisiQuost — o CRM da Sentinela Suite

An AI-powered Universal CRM with **Jarvis**, an assistant that runs entirely on your machine.

**Zero external APIs.** There is no cloud-LLM path in the code: the local intent
engine handles everything, and the app works with the network unplugged. It also
hosts the **Sentinela** parental-control panel — see the
[README da suite](../../README.md).

## What's in it

### CRM foundation
- **Multi-tenant** by workspace (`workspace_id` on every row), JWT + argon2 auth, JWT refresh, membership roles (owner/admin/member/viewer)
- **Entities**: Companies, Contacts, Leads, Opportunities, Pipelines & Stages, Tasks, Meetings, Notes, Activities (append-only timeline), Tags
- **Kanban pipeline** with drag-to-move stage, WIP limits (right-click header), auto-close on Won/Lost, collapsed columns
- **Detail drawer** — click any row → sliding panel with fields + notes (add inline) + activity timeline
- **CSV import** for contacts (drag & drop)
- **Bulk create** endpoints with per-row error reporting
- **Import/export** — every workspace ↔ a portable JSON envelope (with UUID remap when target has data)
- **Optional periodic backup** to disk via `JARVIS_BACKUP_DIR`
- **Rate limiting** on `/auth` and `/jarvis` (in-memory token bucket, opt-out via `RATE_LIMIT_ENABLED=false`)
- **Structured logging** with per-request UUIDs (JSON in prod, human-readable in dev)

### Jarvis assistant (local-first)
- **Bilingual** intent detection (pt-BR / en) with **fuzzy typo tolerance** (`difflib`)
- **Handles offline**: greetings, help, counts, pipeline summary, forecast, overdue tasks, upcoming meetings, today/this week summary, create task/note, mark task done, find/list contacts by company, find company, move opportunity stage, log call/email/sms/whatsapp/chat, reschedule meeting (with tiny NL date parser), activity timeline, search everywhere (unified ILIKE across entities), remember preferences ("call me Alex", "prefer portuguese"), recalculate lead scores
- **Conversation persistence** — server tracks conversations + messages so history reloads
- **Proactive nudges** on `/jarvis/context` — chips over the chat panel that click to fire prompts (overdue pile warning, next meeting, hot lead)
- **No escalation path** — when the local engine cannot handle a request it says so. There is deliberately no cloud fallback: the assistant must behave identically with the network unplugged.

### Automations
- **Lead scoring rules** with 14 operators across fields like `email_domain`, `source`, `score`. Auto-recompute on create/update; bulk recalculate.
- **Workflow engine** — triggers match Activity kind + subject_type + optional `subject.<field>` conditions. Actions: `create_task`, `add_note`, `set_lead_status`, `move_opportunity`. Templates `{{subject_id}}`. Loop guard. Full audit trail (`WorkflowRun`).

### Frontend
Vanilla JS SPA served by the FastAPI itself — no build step. Nav: Dashboard, Contacts, Companies, Opportunities, Leads (with inline Scoring rules builder), Pipeline (kanban), Tasks, Automations.

## Stack

Python 3.11 · FastAPI · SQLModel · SQLite (dev) / PostgreSQL (prod) · Alembic · Vanilla JS+CSS. No AI SDK: the assistant is a local intent engine.

## Quick start (Windows — 1 clique)

Duplo-clique em **`INSTALAR.bat`** na raiz do projeto.

O script detecta o Python (instala via winget se faltar), cria o venv, instala as dependências, aplica as migrations e abre <http://127.0.0.1:8000/> no navegador.

O responsável cria a conta no primeiro acesso (registro na própria tela inicial).

Depois da primeira instalação, use **`INICIAR.bat`** para subir o servidor sem reinstalar.

## Quick start (manual)

```bash
cd apps/crm/backend
python -m venv .venv && .venv\Scripts\activate    # Windows
pip install -r requirements.txt                   # de dentro de apps/crm/backend
cp .env.example .env
uvicorn app.main:app --reload
```

Open <http://localhost:8000/>, register a workspace, click **Seed demo data** to populate it.

API docs at <http://localhost:8000/docs>.

### Database

Dev boots with `SQLModel.metadata.create_all()`. For real deploys use Alembic:

```bash
alembic upgrade head
```

## Export / import

```
GET  /api/v1/workspaces/current/export
POST /api/v1/workspaces/current/import   (JSON envelope body)
POST /api/v1/workspaces/current/seed-demo?force=false
```

Owner/admin only. UUIDs preserved when importing into an empty workspace, regenerated otherwise.

## Layout

```
apps/crm/
├── backend/
│   ├── app/
│   │   ├── api/            HTTP routes
│   │   ├── core/           config, security, logging, middleware
│   │   ├── db/             engine + session
│   │   ├── jarvis/         local_engine, context, tools, runner, date_parser
│   │   ├── models/         SQLModel tables
│   │   ├── schemas/        Pydantic request/response
│   │   └── services/       business logic
│   ├── alembic/            migrations
│   └── tests/              458 tests
├── frontend/               vanilla JS SPA (served by FastAPI)
└── docs/                   ARCHITECTURE.md, ROADMAP.md
```

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md). Items there that assume external APIs (OAuth flows, cloud LLM) are **out of scope** — the zero-external-APIs rule wins over the older roadmap.

## License

TBD.
