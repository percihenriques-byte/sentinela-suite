# Features implementadas (checklist completo)

Cada item foi implementado, tem testes (backend + walkthrough Playwright), e está em produção.

## 🔐 Autenticação e multi-tenancy

- [x] Registro com email + senha + workspace name
- [x] Login via email/senha (argon2)
- [x] JWT access token (1h) + refresh token (14d)
- [x] Botão "⚡ Entrar como demo" — login 1-clique
- [x] Multi-workspace com isolamento total (`workspace_id` em toda query)
- [x] Membership roles: owner / admin / member / viewer
- [x] Logout limpa token + cache localStorage
- [x] Email `.local` NÃO é permitido (validação pydantic) — demo usa `.app`

## 👥 CRM — Contatos

- [x] Listing paginado (200/page) com search por nome/email
- [x] Criar via modal (Enter submete)
- [x] Editar inline via drawer (click no campo)
- [x] Deletar via drawer
- [x] Bulk select + delete + export CSV
- [x] Avatar chip com cor hash-based (initials)
- [x] Quick actions no hover (📧 email, 📞 call)
- [x] NEW badge em contatos criados < 24h
- [x] Import CSV
- [x] Export CSV completo (paginação real, até 5000 rows)

## 🏢 CRM — Empresas

- [x] Listing paginado + search
- [x] Criar / editar / deletar
- [x] Bulk actions
- [x] Campos: nome, domain, industry, size, website, annual_revenue

## 💼 CRM — Oportunidades

- [x] Listing + search + stage filter
- [x] Kanban visual por estágio (drag & drop com mouse)
- [x] Kanban **keyboard reorder** (Space pega, ←→ move, Enter abre) — WAI-ARIA aria-grabbed
- [x] Cards mostram valor + probabilidade (barrinha) + close date
- [x] WIP limits por estágio (right-click header)
- [x] Colunas colapsáveis (Won/Lost colapsados por default)
- [x] Templates de pipeline (instalação 1-clique)
- [x] Auto-close on Won/Lost

## 🎯 CRM — Leads

- [x] Listing separado de contatos (funil pré-conversão)
- [x] Scoring rules com 14 operadores
- [x] Auto-recompute score on create/update
- [x] Bulk recalculate all
- [x] Rules editor inline com CRUD

## 📅 Tarefas

- [x] Listing agrupado por **vencimento** (Atrasadas / Hoje / Amanhã / Semana / Depois / Sem prazo / Concluídas)
- [x] Sort: overdue nearest primeiro, done bottom
- [x] Priority icons 🔥 urgent · ⬆ high · • normal · ⬇ low com cores
- [x] Click-to-complete checkbox (círculo com ✓)
- [x] Line-through em tasks feitas
- [x] Filter chips: open / done / overdue / all
- [x] Empty states diferenciados por filtro

## 📆 Reuniões

- [x] Listing agrupado por dia (Hoje / Amanhã / Esta semana / Depois / Passado)
- [x] Sort: futuras nearest primeiro
- [x] Ícone 📅 em círculo accent-soft
- [x] Badge "▶︎" futura · "✓" passada · "● AGORA" (últimos 90min)
- [x] Highlight `.meeting-now` com border-left accent
- [x] Skeleton loading
- [x] Formato local de data/hora

## 📜 Notas + Timeline

- [x] Notas polymorphic (contact/company/opp/lead)
- [x] Add via input + Enter
- [x] XSS-safe (HTML escapado via textContent)
- [x] Activity timeline no drawer com filter chips por kind

## 📊 Atividades (Activity Feed)

- [x] Feed append-only global
- [x] Kinds traduzidos (Criado / Atualizado / Removido / Ganho / Perdido / Chamada / Email / SMS / WhatsApp / Chat / Mudou etapa)
- [x] Ícones em círculo colorido por severidade (verde=good, azul=info, vermelho=warn)
- [x] Subject types traduzidos (contato/empresa/oportunidade/lead/tarefa/reunião/nota)
- [x] Time ago em PT/EN
- [x] Export CSV

## 🏷 Tags

- [x] CRUD tags (nome + cor)
- [x] Attach polymorphic a qualquer entidade
- [x] Bulk attach/detach

## 🤖 JARVIS (assistente local)

### Intents implementados (80+)
- [x] Saudações (greeting: bom dia / oi / hi / hello / …)
- [x] Ajuda / capacidades
- [x] Contadores (quantos contatos, empresas, etc.)
- [x] Pipeline health (por estágio, valor total, weighted)
- [x] Top N oportunidades (top / top 5 / maiores / melhores)
- [x] Briefing diário (overdue + reuniões hoje + top opp + tip)
- [x] Digest semanal / mensal
- [x] Weekly recap
- [x] Suggest next action
- [x] Momentum check
- [x] Who to call today
- [x] Data quality check
- [x] Hot leads / stale opportunities
- [x] Buscar contato/empresa/oportunidade/lead
- [x] Search everywhere (unified ILIKE)
- [x] Contatos por empresa
- [x] Criar contato / empresa / oportunidade / tarefa / reunião / nota
- [x] Update field (email, phone, priority, etc.)
- [x] Move opportunity to stage
- [x] Log call / email / sms / whatsapp / chat
- [x] Reschedule meeting (parser NL "amanhã 15h")
- [x] Mark task done
- [x] Recalculate lead scores
- [x] Set preferences (tone, preferred_name, language)
- [x] **Undo last** (update ↩️ restore old value; create ↩️ soft-delete)
- [x] Explain last (com tool_calls)
- [x] Read local file (sandboxed to workdir/)
- [x] Scan work dir
- [x] Analyze entity (contact/company/opportunity/lead)
- [x] Set tone (formal/casual/technical/concise)
- [x] Analyze pipeline / opportunity

### Language detection
- [x] `_detect_lang` conta tokens em PT_HINTS + EN_HINTS
- [x] Default PT (produto BR-first) quando empate/zero
- [x] EN_HINTS expandido: weekly, digest, briefing, today, tomorrow, read, file, etc.

### Tone system
- [x] 4 tons: formal (default) / casual / technical / concise
- [x] Cada handler branches por tone
- [x] Persistido via JarvisMemory kv

### Conversation persistence
- [x] JarvisConversation + JarvisMessage
- [x] `conversation_id` mantido no frontend via localStorage
- [x] Listing de conversas + reload histórico
- [x] Search em mensagens

### Proactive nudges
- [x] `/jarvis/context` retorna nudges (overdue warn, next meeting, hot lead)
- [x] Chips renderizados sobre o chat, click dispara prompt

## 🎨 UX / a11y

- [x] Dark mode com toggle
- [x] Landing hero refeita (h1 gigante gradient, feature cards, stats, botão demo)
- [x] Hero i18n PT/EN via `data-i18n`
- [x] Auth page scrollável (bug de body overflow:hidden corrigido)
- [x] Hero KPI destacado ("Pipeline aberto R$ 473.000")
- [x] Skeleton loading em tables + drawer + meetings + tasks
- [x] Recently viewed strip no dashboard
- [x] Row hover quick actions
- [x] Row keyboard nav (↑↓ + Enter)
- [x] Cmd-K palette (search global + contextual actions)
- [x] Backdrop click fecha modal/cmdk/drawer
- [x] Focus restore ao fechar overlay
- [x] role="dialog" + aria-modal em modais
- [x] focus-visible outline
- [x] sr-only utility
- [x] Reduced motion respeitado globalmente
- [x] Print styles (@media print) — dashboard vira relatório limpo
- [x] Top-of-page progress bar (Vercel-style) durante API calls
- [x] Bulk toolbar polida (pill count + danger btn + slideIn)
- [x] Drawer sticky header
- [x] Kanban drop indicator (dashed placeholder)
- [x] NEW badge (< 24h) em entidades novas
- [x] Local footprint widget ("812.0 KB no seu disco · 32 registros")
- [x] Nomes de estágios traduzidos (Prospecting → Prospecção, etc.)
- [x] Drawer header em PT ("Contato" em vez de "Contact")
- [x] Modal Enter submete (via hidden submit btn)

## 📱 Mobile

- [x] Sidebar deslizante com hamburger
- [x] Backdrop scrim
- [x] Auto-close após navegar
- [x] Jarvis FAB (bola gradient)
- [x] KPI em 2 colunas
- [x] Landing hero some, form ocupa tela toda
- [x] Botão demo bem visível
- [x] Cards de reunião empilhados

## 🔄 Import/Export

- [x] Export workspace completo (JSON portable, com UUIDs)
- [x] Import workspace (com UUID remap se conflito)
- [x] Contacts CSV import (drag & drop)
- [x] CSV export por entidade (paginação real até 5000)
- [x] Bulk CSV export por seleção

## ⚙️ Automações

- [x] Workflow engine
- [x] Triggers: Activity kind + subject_type + subject.<field> conditions
- [x] Actions: create_task, add_note, set_lead_status, move_opportunity
- [x] Template strings `{{subject_id}}`
- [x] Loop guard (max 5 workflows por trigger)
- [x] Audit trail (WorkflowRun com input/output/error)
- [x] Toggle enable/disable

## 🔐 Segurança

- [x] argon2-cffi password hash
- [x] JWT access + refresh
- [x] Rate limiting em `/auth` e `/jarvis` (token bucket in-memory)
- [x] Fernet encryption em campos sensíveis (via ENCRYPTED_FIELDS)
- [x] Path escape prevention em `read_local_file` (sandbox workdir)
- [x] XSS via escapeHtml em user content
- [x] CORS configurable
- [x] Password minlength 8 no schema
- [x] Email validation via pydantic email-validator

## 📊 Observabilidade

- [x] Request UUIDs no logging middleware
- [x] Structured JSON logs em prod, human-readable em dev
- [x] `/healthz` endpoint
- [x] Local footprint endpoint (db_bytes + row_counts + workdir_files)

## 🚀 Deploy Windows

- [x] `INSTALAR.bat` — 6 steps, winget guard, venv recovery, health check
- [x] `INICIAR.bat` — poll healthz + LAN IP detection + zero browser launch
- [x] `RODAR.bat` — 1-clique (install ou init)
- [x] `_run_server.cmd` — auxiliar server-only
- [x] Auto-cria pasta `~/Documents/VisiQuost` para workdir
- [x] Auto-gera APP_SECRET_KEY no .env
- [x] pywebview desktop launcher (opcional)

## 🧪 Testes

- [x] 434 pytest passando (backend)
- [x] full_flow.py — 18/18 (auth → nav → CRUD → Jarvis)
- [x] brutal_walkthrough.py — cobertura ampla (Cmd-K, drawer, bulk, kanban, mobile)
- [x] deeper_walk.py — task filters, kbd nav, WIP, kanban kbd, i18n switch
- [x] r4_walk.py — automations, scoring, undo (create), preferences, theme
- [x] r5_edge.py — email dup, unicode, XSS, quotes, rapid nav, Ctrl+/, msg gigante
