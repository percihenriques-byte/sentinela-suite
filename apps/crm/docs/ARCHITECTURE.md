# Architecture

## At a glance

```
┌──────────────────────┐     ┌──────────────────────────────────────────┐
│ Vanilla-JS SPA       │◄────┤ FastAPI (uvicorn)                        │
│ frontend/*           │     │  ├─ Auth (JWT + argon2)                  │
│                      │     │  ├─ CRM CRUD + bulk + pagination         │
│  ── Dashboard        │     │  ├─ Workspace export/import + seed       │
│  ── Contacts/…       │     │  ├─ Lead scoring rules + evaluator       │
│  ── Kanban           │     │  ├─ Workflow engine (Activity-triggered) │
│  ── Detail drawer    │     │  ├─ Tags + Integrations (Fernet tokens)  │
│  ── Automations      │     │  └─ Jarvis                                │
│  ── Integrations     │     │       ├─ LocalJarvis  (offline, primary) │
│  ── Jarvis chat +    │     │       │    ├─ 25+ intent handlers         │
│     nudges chips     │     │       │    ├─ Tool registry                │
│                      │     │       │    └─ NL date parser (offline)     │
│                      │     │       └─ Anthropic runner (optional)      │
└──────────────────────┘     └──┬───────────────────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │ SQLModel / SQLAlchemy 2 │
                    │  SQLite (dev)           │
                    │  Postgres (prod)        │
                    │  Alembic migrations     │
                    └─────────────────────────┘
```

Requests flow: Middleware chain (RequestId → RateLimit → CORS) → route → service → SQLModel. Every mutation on a CRM object emits an `Activity` row; the workflow runtime evaluates active workflows synchronously and can create tasks/notes/status changes. Jarvis reads the same tables through a shared `ToolContext`.



## Stack decisions

| Layer | Choice | Reason |
|-------|--------|--------|
| Backend | Python 3.11+ / FastAPI | Async-native, OpenAPI-first, ergonomic for AI + CRUD |
| ORM | SQLModel (SQLAlchemy 2 + Pydantic) | Single model = table + schema, less duplication |
| Dev DB | SQLite | Zero-setup local dev, offline capable |
| Prod DB | PostgreSQL | JSONB, full-text search, row-level security |
| Auth | JWT + argon2 password hashing | Stateless, well-supported |
| Frontend | Flutter (planned) | One codebase → web, Android, desktop |
| AI | Anthropic Claude API | Long context, tool use, reliable structured output |
| Task queue (future) | Celery + Redis | Standard for background workflows |

## Multi-tenant model

Every domain row carries a `workspace_id`. A user belongs to one or more workspaces via `WorkspaceMember` with a role (`owner`, `admin`, `member`, `viewer`). This lets a single installation host many businesses without physical DB separation, while still enabling row-level security policies in Postgres later.

## Core domain

CRM entities live under `backend/app/models/`. The canonical set:

- **Identity**: `User`, `Workspace`, `WorkspaceMember`
- **Directory**: `Company`, `Contact`
- **Pipeline**: `Lead`, `Opportunity`, `Pipeline`, `PipelineStage`
- **Work**: `Task`, `Meeting`, `Note`, `Activity`
- **Commerce**: `Product`, `Quote`, `Contract`, `Invoice`
- **Content**: `Document`, `File`, `Tag`, `CustomField`, `CustomFieldValue`

Every entity carries `id` (UUID), `workspace_id`, `created_at`, `updated_at`. Soft-delete via `deleted_at` for auditability.

## Jarvis

**Design constraint:** Jarvis must be fully usable **without any external APIs**. The local engine is the primary path. Claude (or any cloud LLM) is an optional enhancement, never a hard requirement.

`backend/app/jarvis/` is where the assistant lives. Two tiers:

### Tier 1 — Local engine (always available)

`local_engine.py` runs entirely on-device with no network calls. It:

  * classifies intent via keyword + regex patterns (bilingual: pt-BR / en),
  * routes to a handler that reads the workspace snapshot or invokes an existing tool,
  * returns natural-language replies built from real data.

Handled intents include: greetings, help, entity counts, pipeline summary, overdue tasks, upcoming meetings, open opportunities, task creation ("create task: …"), and contact search. Every new capability starts here.

### Tier 2 — Cloud LLM (optional bonus)

`runner.py` wraps the Claude tool-use loop. Only consulted when Tier 1 explicitly escalates *and* `ANTHROPIC_API_KEY` is configured. Failure of Tier 2 never breaks the endpoint — the user gets the Tier 1 reply plus a note.

### Shared components

1. **Context builder** (`context.py`) — workspace snapshot (open opportunities, overdue tasks, upcoming meetings) that primes both tiers.
2. **Tool registry** (`tools.py`) — declarative tools: `search_contacts`, `create_task`, `summarize_pipeline`, `list_open_opportunities`. Reused by both tiers.
3. **Memory** — per-user preference store (`JarvisMemory` table) so Jarvis learns tone, defaults, and priorities over time.

Jarvis never bypasses the CRM's authorization layer — every tool call routes through the same service layer that HTTP endpoints use, so RLS and audit logging apply uniformly.

## Security posture

- Argon2id for passwords, JWT for session, refresh tokens with rotation.
- All secrets via env vars (`.env` gitignored, `.env.example` checked in).
- CORS strict-by-default.
- Rate limiting on auth + Jarvis endpoints.
- Audit log table (`AuditEvent`) records who did what and when.
- Encryption at rest for tokens/credentials of connected external accounts (Fernet, key from env).

## Extensibility

- **Custom fields**: per-workspace, per-entity, typed (`text`, `number`, `date`, `select`, `multi_select`, `json`). Stored in `CustomFieldValue` as JSONB.
- **Tags**: many-to-many polymorphic.
- **Webhooks**: outbound event delivery for external automation.
- **Integrations** (planned modules, not yet implemented): Google Workspace, Microsoft 365, WhatsApp Business, Telegram, SMS providers.
