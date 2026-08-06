# Provas de que está funcional

## Backend pytest

```
$ cd backend && .venv/Scripts/python.exe -m pytest -q
............................................................................. [ 16%]
............................................................................. [ 33%]
............................................................................. [ 49%]
............................................................................. [ 66%]
............................................................................. [ 82%]
............................................................................. [ 99%]
..                                                                              [100%]
434 passed, 1 warning in 52.68s
```

Cobre: models, migrations, services, todos os endpoints REST, workflow engine, lead scoring,
100+ intents do Jarvis (create/update/undo/greeting/briefing/digest/search/…).

## Walkthroughs Playwright ("as user")

Cada walkthrough usa Chromium headless com `slow_mo=60-120ms` (simula tempo humano),
tira screenshots em cada tela, captura JS errors + HTTP 4xx/5xx.

### full_flow.py — 18/18

```
=== FULL FLOW: 18/18 ===
  OK | Auth page loads
  OK | Hero h1 visible
  OK | 4 feature cards
  OK | Stats visible
  OK | Demo button visible
  OK | Demo login opens app
  OK | Nav contacts: #contacts-table
  OK | Nav companies: #companies-table
  OK | Nav opportunities: #opportunities-table
  OK | Nav leads: #leads-table
  OK | Nav kanban: .kanban-col
  OK | Nav tasks: #task-list
  OK | Nav meetings: #meetings-list
  OK | Contatos demo carregados (10)
  OK | Add contact modal opens
  OK | New contact appears
  OK | Jarvis responds (1 msgs)
  OK | Kanban cards (5)
JS errors: 0
4xx/5xx (excl 401/409): 0
```

### brutal_walkthrough.py — 0 issues

Cobre Cmd-K search, drawer inline edit, add note via Enter, bulk select + clear,
filter search, task complete, kanban drag & drop, Jarvis multi-intent (resumo,
top opps, briefing), CSV export, meetings, print styles, recently viewed,
mobile hamburger.

```
FRICTION REPORT: 0 issues
JS errors: 0
HTTP 4xx/5xx (excl 401/409): 0
```

### deeper_walk.py — 0 issues

Cobre task filter chips, kanban WIP context menu, kanban keyboard reorder
(Space + arrows), row Arrow keyboard nav (↑↓ + Enter), criar oportunidade,
Ctrl+K palette com actions, onboarding, language switch PT↔EN, re-login após
logout, refresh dashboard.

```
FRICTION: 0 issues
JS: 0
HTTP: 0
```

### r4_walk.py — 0 issues

Cobre nav "Mais" menu, Automations page, scoring rules, meu dispositivo,
popular demo seed, undo intent via Jarvis (both update AND create),
preferences (tom casual), delete contact via drawer, import CSV, export JSON,
novo workflow, busca contato Ada, kanban WIP right-click, theme toggle
(dark ↔ light).

```
FRICTION: 0
JS: 0
HTTP: 0
```

### r5_edge.py — 0 issues

Edge cases: email duplicado (409 correto), contato com unicode/emoji, XSS em
nota (escapado), search com quotes/caracteres especiais, rapid nav (14 clicks
em 2s), Ctrl+/ focus Jarvis, task com due passado, Jarvis input vazio,
Jarvis msg gigante (200x "visiquost"), Escape em vários overlays.

```
FRICTION: 0
JS: 0
HTTP 5xx: 0
```

## Bugs pegos e corrigidos ao longo do path

Foram muitos loops de "walkthrough → achou bug → fix → commit". Alguns dos reais:

| # | Bug | Descoberto por |
|---|---|---|
| 1 | `demo@visiquost.local` rejeitado por pydantic (.local reservado) | full_flow (login demo falhou) |
| 2 | `body { overflow: hidden }` travava scroll da landing | Perci reportou "não consigo scrollar" |
| 3 | Cache do browser servindo versão velha | Perci reportou "não muda" → `_NoCacheStatic` |
| 4 | Auth landing hardcoded PT quando lang=EN | deeper_walk |
| 5 | Jarvis default lang=EN mesmo com produto BR | brutal_walkthrough ("briefing" respondia EN) |
| 6 | "top oportunidades" (sem número) → não reconheci | brutal_walkthrough |
| 7 | CSV export batia `limit=1000` → 422 silencioso | brutal_walkthrough (HTTP monitoring) |
| 8 | Greeting perdia palavra "local" ("locais" ≠ "local") | pytest test_jarvis_tone_pt |
| 9 | Drawer header "Contact" em PT | user_walkthrough |
| 10 | Stages "Prospecting/…" em EN mesmo com locale PT | user_walkthrough |
| 11 | Whitespace duplo "808.0  KB" | user_walkthrough |
| 12 | Enter no modal criar contato não submetia | user_walkthrough |
| 13 | Undo desfazia só update, não create | r4_walk (regressão que virou feature) |
| 14 | INSTALAR.bat: `"py -3"` entre aspas → comando não reconhecido | Perci `Could not open requirements file` |
| 15 | INSTALAR.bat: `for /f "%%d.%%d"` parser err | Perci |
| 16 | INSTALAR.bat: `echo (nao critico)` fechava if-block | Perci |
| 17 | INICIAR.bat: browser abria antes do server pronto | Perci "conexão recusada" |

Todos corrigidos e verificados por re-run do teste que pegou o bug.

## Executar os testes na sua máquina

```bash
# Backend
cd backend
.venv/Scripts/python.exe -m pytest -q

# Walkthroughs (server precisa estar rodando em :8000)
python -m uvicorn app.main:app --port 8000 &
python ../scratchpad/full_flow.py
python ../scratchpad/brutal_walkthrough.py
python ../scratchpad/deeper_walk.py
python ../scratchpad/r4_walk.py
python ../scratchpad/r5_edge.py
```

(Os scripts de walkthrough estão no `~/AppData/Local/Temp/claude/.../scratchpad/` — pode
copiar pro repo se quiser rodar recorrente.)
