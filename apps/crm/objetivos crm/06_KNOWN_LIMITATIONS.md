# Limitações conhecidas e decisões conscientes

## Coisas que NÃO existem (intencionalmente)

### Cloud LLM em runtime
- Jarvis é 100% local (regex + fuzzy + slot filling).
- Havia um caminho de escalação pra Anthropic Claude quando `ANTHROPIC_API_KEY` setado,
  mas atualmente **desligado** por decisão do Perci (regra ZERO APIs).
- Sem esse fallback, msgs bizarras/ambíguas ganham "Não reconheci — sugiro estes comandos".

### OAuth / SSO / login social
- Só email + senha (argon2). Login demo pré-criado (`demo@visiquost.app` / `demo1234`).
- Sem "Login with Google", sem "Login with Microsoft".

### Integração com Google Calendar / Outlook
- Substituído por: usuário arrasta `.ics` na pasta workdir, Jarvis lê.
- Substituído por: usuário arrasta `.csv` de contatos, Jarvis importa.
- Não tem sync bidirecional; é one-way import.

### PostgreSQL / cloud DB
- Estrutura pronta pra Postgres (sqlmodel + alembic), mas default é SQLite.
- Ninguém testou em prod com Postgres.

### Email real / SMTP
- "Email" no CRM é um LOG (activity kind), não um envio real.
- Botão "Email" no drawer abre `mailto:` (cliente do usuário).

### Notificações push
- Não existem. Só toast in-app.
- "Inbox" só mostra atividades recentes (unread cursor via localStorage).

## Limitações reais que poderiam ser melhoradas

### 1. Fresh browser reload perde `conversation_id`
`state.conversation_id` é persistido em localStorage → OK. Mas se limpar localStorage OU
navegar em nova aba anônima, cada mensagem cria nova conversa e "desfaz" não acha o create.

### 2. Undo só desfaz última ação
Não há stack de undo/redo. `desfaz` sempre reverte a última mutação reversível na
conversa atual.

### 3. Kanban WIP prompt usa `window.prompt()`
Feio comparado com modal custom. Perci não reclamou ainda, deixa como está.

### 4. Search não tem fuzzy tolerance
`ILIKE '%q%'` — case insensitive mas exato. "Alab" não acha "Alan Turing".

### 5. Jarvis não escreve para múltiplos idiomas
`_detect_lang` retorna pt OU en. Reply é em PT ou EN. Sem espanhol, francês, etc.

### 6. Bulk delete não tem "desfazer"
Diferente do undo de criação single, bulk-delete não é revertível via `desfaz`.

### 7. Sem export PDF
Print (Ctrl+P) dá relatório em HTML → PDF via impressora, mas sem export direto.

### 8. Mobile: kanban não é touch-friendly pra drag
Cards têm `draggable=true` (mouse), mas em touch-only não dá pra reordenar. Fallback:
tap no card → drawer → "mover pra stage X" via Jarvis.

### 9. Mais de 1 workspace requer UI
Backend suporta múltiplos workspaces por user, mas UI só mostra o primeiro
(state.workspace = wss[0]). Sem workspace switcher.

### 10. Sem colaboração real-time
Se dois usuários (do mesmo workspace via LAN) editam ao mesmo tempo, último gravado ganha.
Sem CRDT, sem WebSocket sync.

## Perguntas em aberto

### Deve suportar Postgres em prod?
Está estruturado, mas ninguém testou. Se sim, precisa:
- CI que roda pytest contra ambos SQLite e Postgres
- Docker compose com pg + volume
- Alembic scripts verificados em pg

### Deve empacotar como app Windows (`.exe`)?
Tem `pywebview` + `backend/desktop.py` que envelopa em janela WebView2 nativa.
Não é usado por default porque Perci reclamou de "browser externo abrindo".
Poderia virar `pyinstaller --onefile` mas ~150MB.

### Multi-idioma no dicionário
Só PT e EN atualmente. Se quiser ES/FR, precisa expandir os dicts em `translations.js`.
