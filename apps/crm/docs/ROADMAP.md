# Roadmap

Tracks incremental progress across autonomous loop ticks. Each tick should complete at least one line here or add follow-ups.

## Phase 1 — Foundation (in progress)

- [x] Repo layout, docs, stack decision
- [x] Backend package scaffold
- [x] Config + settings module
- [x] SQLModel base + engine + session (StaticPool for `:memory:` in tests)
- [x] Core identity models (User, Workspace, WorkspaceMember)
- [x] Core CRM models (Company, Contact, Lead, Opportunity, Pipeline, Stage, Task, Note, Activity)
- [x] Jarvis skeleton (context builder, tool registry, runner stubs)
- [x] Auth endpoints (register, login, refresh, me)
- [x] Workspace resolution dep (`X-Workspace-Id` header + membership check)
- [x] Workspace-scoped CRUD helpers (`scoped_query`, `get_or_404`, `soft_delete`, `count_from`)
- [x] Activity logging helper (`log_activity`)
- [x] Company CRUD endpoints
- [x] Contact CRUD endpoints (validated company_id)
- [x] Lead CRUD endpoints
- [x] Lead → Opportunity conversion flow (with optional Company creation)
- [x] Pipeline bootstrap + default stages (Prospecting → Won/Lost)
- [x] Opportunity CRUD endpoints (stage move → auto-close on Won/Lost, syncs probability)
- [x] Task CRUD endpoints (auto-stamps completed_at)
- [x] Meeting CRUD endpoints (validates ends_at > starts_at)
- [x] Note CRUD endpoints (polymorphic related_* filters)
- [x] Pagination wrapper `Page[T]` with total counts across all list endpoints
- [x] Integration tests: CRUD, workspace isolation, lead conversion, stage transitions, task lifecycle, meeting window, note filters
- [ ] Cursor pagination for very large collections
- [ ] Alembic migrations (currently create_all)
- [ ] Structured logging with request IDs

## Phase 2 — Jarvis MVP (in progress)

**Constraint:** Jarvis must work without any external APIs. There is no cloud tier — items abaixo que dependam de uma sao historicos e estao fora de escopo.

- [x] Chat endpoint `/jarvis/chat` — local-first, LLM optional
- [x] Context snapshot endpoint `/jarvis/context`
- [x] Local engine (offline, bilingual pt/en) — intents: greeting, help, counts, summarize pipeline, overdue tasks, upcoming meetings, open opportunities, create task, find contact
- [x] More local intents: create note, mark task done, find company, move opportunity stage, activity timeline, today summary
- [x] Diacritic-insensitive normalization + fuzzy match helper (`difflib`) infrastructure
- [x] Conversation persistence (`JarvisConversation` + `JarvisMessage` models + endpoints)
- [x] Persisted history auto-loaded on next turn (client doesn't need to re-send)
- [x] Per-user JarvisMemory learning: "remember: X", "call me Alex", "prefer portuguese" — persists to JarvisMemory and surfaces on next turn
- [x] `list_preferences` intent ("what do you remember", "preferences")
- [x] `log_interaction` intent (call/email/sms/whatsapp/chat/conversa) — writes an Activity row
- [x] `reschedule_meeting` tool + natural-language intent ("reschedule Sync to tomorrow 3pm")
- [x] Tiny offline NL date parser (today/tomorrow/next monday/HH:MM/3pm, pt+en)
- [x] `forecast` intent + tool — buckets open opportunities by expected_close_date × probability
- [x] `list_contacts_by_company` intent + tool ("who works at Acme")
- [x] Wire fuzzy_keywords on top intents (summarize_pipeline, overdue_tasks, upcoming_meetings, open_opportunities, forecast) — tolerates common typos
- [x] `search_everywhere` tool + intent — unified ILIKE across contacts/companies/leads/opportunities/notes
- [x] `list_activity_for_subject` tool + `/activities` endpoint (used by frontend detail drawer)
- [x] `week_summary` tool + intent + dashboard widget
- [x] Proactive nudges in `/jarvis/context` (overdue task piles, upcoming meeting, hot leads) surfaced as chips
- [x] Tags CRUD (`/tags` + attach/detach + `tags/for/{subject_type}/{id}`) + idempotent name reuse
- [x] Bulk create endpoints (`/contacts/bulk`, `/companies/bulk`) with per-row error reporting
- [x] CSV import UI on Contacts page (client-side parser, header normalization, name-split heuristic)
- [x] Bulk delete endpoints (`/contacts/bulk-delete`, `/companies/bulk-delete`) with per-id error tolerance
- [x] `tag_entity` local Jarvis intent ("tag Ada as VIP") — upserts tag + attaches
- [x] Phase 5 plumbing: ExternalAccount model + Fernet-encrypted token storage + `/integrations/connect|list|disconnect|peek` endpoints (google/microsoft/slack/manual providers; no live network yet)
- [x] Integrations nav page on frontend — list connected accounts + manual "Paste token" form
- [x] Composite indexes on hot query paths via Alembic 0002 (workspace+deleted, Activity(subject_type, subject_id), etc.)
- [x] Review pass — bug fixes: `_field_is_optional` now checks annotation for `Union[..., None]` (previously treated defaulted booleans as nullable and could clobber them); `find_contact` intent regex disambiguated so bare word "contact" no longer hijacks; bulk-create endpoints use SAVEPOINTs so a single bad row doesn't poison the outer transaction
- [ ] Optional: SQLite FTS5 for ranked local search (upgrade path from ILIKE)
- [ ] Optional: local embedding-based semantic search (no cloud)
- [ ] Optional: SSE streaming endpoint for chat responses (works with both tiers)
- [ ] Guardrail: cloud LLM tools must respect workspace_id from ToolContext, never accept it from the model

## Phase 3 — Automations (in progress)

- [x] Lead scoring rules + CRUD + auto-recompute + Jarvis intent
- [x] Lead scoring rule builder UI (frontend, under Leads → Scoring rules)
- [x] Workflow engine tables: `Workflow`, `WorkflowStep`, `WorkflowRun`
- [x] Workflow runtime: synchronous evaluation after `log_activity` commits; trigger by kind + subject_type + conditions (activity-level or `subject.<field>`); actions `create_task` / `add_note` / `set_lead_status` / `move_opportunity`; template substitution (`{{subject_id}}` etc.); loop guard (thread-local flag + `workflow.` prefix skip)
- [x] Workflow CRUD endpoints (`/workflows`) + run history (`/workflows/{id}/runs`)
- [ ] Follow-up scheduler as a preset workflow the demo seed ships
- [ ] Workflow builder UI on the frontend

## Phase 4 — Frontend (in progress)

- [x] Minimal vanilla-JS single-page app under `frontend/` — login/register, dashboard KPIs, contacts/companies/opportunities/tasks tables, Jarvis chat panel, create modals
- [x] Served by FastAPI static mount (`/` → frontend/index.html)
- [x] Auth persistence in localStorage; conversation_id persistence
- [x] Pipeline kanban board with drag-to-move-stage (uses PATCH stage_id) + collapsed-by-default Won/Lost columns + per-stage WIP limits (right-click header) + click card to open detail drawer
- [x] Import/export UI in sidebar (download JSON + file picker restore with confirm)
- [x] Detail drawer for Contact / Company / Opportunity / Lead — fields + notes (add inline) + activity timeline; open by clicking a table row
- [x] Leads nav page with status pills + inline scoring rule builder
- [x] "Seed demo data" button (populates a realistic sample dataset)
- [x] Automations nav page — list workflows, enable/disable, delete, run history, JSON editor for trigger + steps
- [x] Dashboard "This week" widget (opps closing, weighted pipeline, tasks due, meetings)
- [x] Jarvis proactive nudges — chips over the chat panel that click to fire suggested prompts (overdue task warnings, next meeting, hot lead alert)
- [ ] Later: replace with Flutter for Android/Desktop parity

## Phase 5 — Integrations (foundation in place)

- [x] `ExternalAccount` model + Fernet field encryption for tokens
- [x] `/integrations` endpoints — connect (manual token paste), list, disconnect, decrypt-check
- [ ] Real OAuth flows for Google / Microsoft (authorize URL, callback, token refresh)
- [ ] Email (IMAP/SMTP)
- [ ] Google Calendar / Outlook Calendar sync
- [ ] WhatsApp Business API
- [ ] Telegram Bot API

## Cross-cutting (ongoing)

- [x] Audit logging via `Activity` on every write (created/updated/deleted/stage_changed/lead_converted/note_added)
- [x] Rate limiting middleware (in-memory token bucket per IP+prefix; stricter on /auth/*)
- [x] Structured logging + request IDs (JSON in prod, human in dev; contextvar propagates request_id/user_id to every log)
- [x] Test coverage via pytest-cov (wired in CI)
- [x] CI pipeline (GitHub Actions: pytest against sqlite in-memory + frontend asset check)
- [x] Workspace export/import (JSON envelope; UUID remap when target has data)
- [x] Alembic bootstrap (env.py + versions/0001_initial.py; `alembic upgrade head` documented in README)
- [x] Optional periodic on-disk workspace backups (env var `JARVIS_BACKUP_DIR` + interval)
- [ ] SQLite FTS5 index for contacts/companies/notes (local ranked search, upgrade over current ILIKE)

## Review passes (bug-fix log)

- [x] Tick 17: `_field_is_optional` annotation check (was clobbering bool fields with None), `find_contact` regex disambiguation (bare "contact" no longer hijacked), bulk endpoints wrap each row in SAVEPOINTs
- [x] Tick 18: `parseCsv` strips UTF-8 BOM (Excel exports), `_CREATE_TASK_RE` accepts English "a"/"new" articles, frontend auto-logs out on 401, Fernet decrypt logs WARNING on invalid tokens (silent key-rotation issues become visible), `_load_subject` cleaned into a dispatch table
- [x] Tick 19: **lead score drift bug** — updating a scored field previously added the new rule's delta on top of the stored score (10 → 15 → 20…); now resets to 0 unless the caller sets `score` explicitly. Added `email-validator` to requirements (Pydantic `EmailStr` needs it). Rate limiter reads `X-Forwarded-For` so proxied deployments don't all share one IP.
- [x] Tick 20: `cors_origins` empty env now falls back to localhost default instead of silently disabling all CORS; workflow template substitution accepts `{{ key }}` with whitespace (was rendering verbatim); rate-limit bucket sentinel changed from `0.0` to `None` (theoretical collision with early-boot `monotonic()`); `export_workspace` uses timezone-aware `datetime.now(utc)` (Python 3.12 deprecated naive `utcnow()`).
- [x] Tick 21: corrupted workflow `trigger_json` now logs WARNING instead of silent skip; `WorkflowStep` list sort adds secondary key on `created_at` so multiple steps sharing `order_index=0` execute in a stable insertion order; new Alembic 0003 adds a UNIQUE index on `TagLink(workspace_id, tag_id, subject_type, subject_id)` and `attach_tag` catches `IntegrityError` to keep the endpoint idempotent under races.
- [x] Tick 22: **NL date parser `3:30 pm` bug** — the 24h regex ran first and swallowed `3:30` before the AM/PM pattern got a shot, so pm markers were silently dropped and reschedules landed at 3am. Pattern order fixed. `verify_password` now catches the argon2 `Argon2Error` base class so a corrupted-hash column returns a clean 401 instead of a 500.
- [x] Tick 23: **PATCH `/opportunities/{id}` cross-pipeline 400** — sending only `pipeline_id` reused the old `stage_id` against the new pipeline and always failed the resolver. Now falls through to the first stage of the new pipeline when the caller doesn't pick one. `update_meeting` returns 400 (not 500) when a client sends `{"starts_at": null}`. Workflow `move_opportunity` action logs a WARNING when the target stage doesn't exist (previously silent).
- [x] Tick 24: **LLM history sanitizer** — dropping fallback assistant turns could leave two consecutive user turns in the history payload, which the Anthropic API rejects. New `_sanitize_history` enforces strict user/assistant alternation, drops leading assistant turns and trailing unpaired user turns so the runner always appends its user message onto a valid tail.
- [x] Tick 25: **cross-workspace FK guard on `convert_lead`** — caller-supplied `company_id` / `pipeline_id` weren't tenant-checked, so a request could stitch a foreign workspace's entity into the new contact/opportunity. Now validated up front, 404 on mismatch. Workflow `set_lead_status` also logs a WARNING when the payload has an invalid status string.
- [x] Tick 26: **systematic cross-workspace FK sweep** — new `crud.verify_scoped_exists` helper, applied to every remaining FK input on `/opportunities` (contact_id, company_id — create + update), `/notes` (related_contact_id/company_id/opportunity_id/lead_id — create + update), `/tasks` (all four related_* fields — create + update), `/meetings` (related_contact_id, related_opportunity_id — create + update). All return 404 on cross-tenant references.
- [x] Tick 27 (**live-server pass**): actually ran the app + tests. Fixed **7 real bugs found only by execution**: (1) `_forecast` compared SQLite-naive datetime to aware `now`, TypeError; (2) my previous `verify_password` fix caught the wrong argon2 base class — corrupted-hash login still 500'd; (3) `cors_origins` validator never ran because pydantic-settings 2.x json-decodes List-typed env vars first — needed `Annotated[List[str], NoDecode]`; (4) test emails on `.test` TLD rejected by email-validator 2.3; (5) `workspace_io` import failed with `str has no attribute hex` (UUID) + `SQLite DateTime type only accepts Python datetime` — added coercion; (6) workspace import id collision when data lives in the shared DB — always remap now; (7) `_reschedule_meeting` mixed tz-aware/naive datetimes → TypeError, and the `weekly` word in "Nebula weekly sync" hijacked the `week_summary` intent instead of `reschedule_meeting`.
- [x] All 140 tests pass. Uvicorn boots. Frontend serves at `/`. Backup scheduler verified end-to-end (writes 28KB envelope per workspace per interval).
- [x] Tick 28 (**live-server pass 2**): probed workflow runtime end-to-end (create workflow → post lead → run + task materialized with `{{subject_id}}` substituted), tags idempotent attach, kanban stage moves. Found + fixed 2 real bugs: (1) opps moved to Won/Lost kept their old probability (10% Prospecting → 10% Won) instead of snapping to 100/0 — huge weighted-pipeline error; (2) `_forecast` bucket boundary: on Sundays `end_of_week` was set to "right now" so every future close_date fell into next_month. Now anchored to end-of-Sunday. 144/144 tests pass.
- [x] Tick 29 (**live-server pass 3**): **SQL LIKE wildcard leak** — user-supplied search input flowed straight into `%{q}%` ilike patterns, so a search for `_` matched any single character and `%` returned the whole table. Not exploitable (parameterized) but semantically wrong. New `crud.like_escape` helper + `escape="\\"` applied everywhere ilike consumes user input: `/contacts?q=`, `/companies?q=`, and 9 spots in `jarvis/tools.py` (`search_contacts`, `search_companies`, `search_everywhere`, `mark_task_done`, `move_opportunity_stage`, `log_interaction`, `tag_entity`, `list_contacts_by_company`, `reschedule_meeting`). Also probed and confirmed working: workflow chains + loop guard, cross-workspace 404, export→import round-trip, bulk delete with per-id error reporting, UTF-8 unicode search, empty-workspace intent handling for all 12 intents.
