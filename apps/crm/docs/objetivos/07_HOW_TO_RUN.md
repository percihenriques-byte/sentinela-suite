# Como rodar

## Primeira vez (fresh install)

1. Clone o repo:
   ```
   git clone https://github.com/percihenriques-byte/sentinela-suite.git
   cd sentinela-suite
   ```
2. Duplo-clique em **`RODAR.bat`** (ou `INSTALAR.bat`).
   - Detecta Python (instala via winget se falta)
   - Cria `apps/crm/backend/.venv`
   - `pip install -r requirements.txt` (rodado de dentro de `apps/crm/backend`)
   - Alembic migrations
   - Cria `~/Documents/VisiQuost` como workdir
   - Auto-invoca `INICIAR.bat`
3. Terminal abre e mostra:
   ```
   ================================================
     VisiQuost - servidor local
   ================================================
     No PC:      http://127.0.0.1:8000/
     No celular: http://192.168.0.47:8000/   (mesma Wi-Fi)

     Copie a URL acima e cole no seu navegador.
     Para parar: feche esta janela (ou Ctrl+C aqui).
   ================================================
   ```
4. Abre no browser (Chrome / Edge / Brave / Firefox).

## Primeiro acesso

O responsável cria a conta no primeiro acesso (registro na própria tela inicial).

## Voltas seguintes

- **`INICIAR.bat`** — só sobe server (não reinstala nada)

## Rodando manualmente (dev)

> **Importante:** todos os comandos abaixo rodam de **dentro de `apps/crm/backend`**.
> Da raiz do monorepo falha — lá não existe `backend/`, e `pip install -r backend/requirements.txt`
> termina em `Could not open requirements file`.

```bash
cd apps/crm/backend
python -m venv .venv
.venv\Scripts\activate         # Windows
pip install -r requirements.txt      # de dentro de apps/crm/backend
copy .env.example .env

# Gera SECRET_KEY aleatória:
python -c "import secrets;print('APP_SECRET_KEY=' + secrets.token_urlsafe(48))" >> .env

# Cria banco + migrations:
python -m alembic upgrade head

# Popula demo (opcional):
python scripts/bootstrap.py

# Sobe server:
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Rodar backend tests

```bash
cd apps/crm/backend
.venv/Scripts/python.exe -m pytest -q
# ou
.venv/Scripts/python.exe -m pytest -v tests/test_smoke.py
```

## Rodar walkthroughs (Playwright)

Precisa instalar browsers do Playwright uma vez:
```bash
cd apps/crm/backend
.venv/Scripts/python.exe -m pip install playwright
.venv/Scripts/python.exe -m playwright install chromium
```

Depois, com server rodando em :8000:
```bash
python full_flow.py     # 18 checks E2E
python brutal_walkthrough.py  # Cmd-K, drawer, bulk, kanban, mobile
python r5_edge.py       # edge cases (unicode, XSS, quotes, rapid nav)
```

Os scripts estão em `~/AppData/Local/Temp/claude/.../scratchpad/` — copie pro repo se
quiser rodar recorrente.

## Estrutura do repo

```
sentinela-suite/
└── apps/crm/
    ├── INICIAR.bat, INSTALAR.bat, RODAR.bat  — launchers Windows
    ├── README.md                              — visão geral
    ├── docs/                                  — ARCHITECTURE.md, ROADMAP.md
    ├── docs/objetivos/                        — esta pasta (log pro Fable)
    ├── backend/
    │   ├── app/                               — código FastAPI
    │   ├── tests/                             — pytest
    │   ├── alembic/                           — migrations
    │   ├── scripts/bootstrap.py               — cria demo user + workspace
    │   ├── _run_server.cmd                    — auxiliar do launcher
    │   ├── desktop.py                         — pywebview launcher (opcional)
    │   ├── requirements.txt
    │   └── .venv/                             — (gitignored) venv local
    └── frontend/
        ├── index.html                         — single page
        └── assets/
            ├── app.js                         — ~5000 linhas
            └── app.css                        — ~1500 linhas
```

## Portas

- **8000** — HTTP (uvicorn) — só essa. Sem HTTPS local (dev).
- Se 8000 estiver em uso: edite `INICIAR.bat` linha `PORT=8000` OU mate o processo antigo.

## Reset completo

Se algo travar horrível:
```bash
# Para tudo:
taskkill /F /IM python.exe

# Apaga DB:
del apps\crm\backend\jarvis_crm.db

# Apaga venv (só se estiver corrompido):
rmdir /s /q apps\crm\backend\.venv

# Re-instala do zero:
INSTALAR.bat
```

## Portas + Firewall

Se Windows Firewall bloquear (raro em loopback), permita quando pedir. Pra celular acessar
via LAN, aceite o prompt de "Rede Privada" na primeira execução.
