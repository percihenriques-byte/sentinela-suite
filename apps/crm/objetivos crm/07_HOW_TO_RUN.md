# Como rodar

## Primeira vez (fresh install)

1. Clone o repo:
   ```
   git clone https://github.com/percihenriques-byte/visiquost-crm.git
   cd visiquost-crm
   ```
2. Duplo-clique em **`RODAR.bat`** (ou `INSTALAR.bat`).
   - Detecta Python (instala via winget se falta)
   - Cria `backend/.venv`
   - `pip install -r backend/requirements.txt`
   - Alembic migrations
   - Bootstrap: cria user demo, workspace demo, popula 30+ registros
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
4. Abre no browser (Chrome / Edge / Brave / Firefox) e clica **⚡ Entrar como demo**.

## Login demo

- Email: `demo@visiquost.app`
- Senha: `demo1234`

## Voltas seguintes

- **`INICIAR.bat`** — só sobe server (não reinstala nada)

## Rodando manualmente (dev)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate         # Windows
pip install -r requirements.txt
copy .env.example .env

# Gera SECRET_KEY aleatória:
python -c "import secrets;print('APP_SECRET_KEY=' + secrets.token_urlsafe(48))" >> .env

# Cria banco + migrations:
python -m alembic upgrade head

# Popula demo (opcional):
python scripts/bootstrap.py

# Sobe server:
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Rodar backend tests

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q
# ou
.venv/Scripts/python.exe -m pytest -v tests/test_smoke.py
```

## Rodar walkthroughs (Playwright)

Precisa instalar browsers do Playwright uma vez:
```bash
cd backend
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
visiquost-crm/
├── INICIAR.bat, INSTALAR.bat, RODAR.bat  — launchers Windows
├── README.md                              — visão geral
├── docs/                                  — ARCHITECTURE.md, ROADMAP.md
├── objetivos crm/                         — esta pasta (log pro Fable)
├── backend/
│   ├── app/                               — código FastAPI
│   ├── tests/                             — 434 pytest
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
del backend\jarvis_crm.db

# Apaga venv (só se estiver corrompido):
rmdir /s /q backend\.venv

# Re-instala do zero:
INSTALAR.bat
```

## Portas + Firewall

Se Windows Firewall bloquear (raro em loopback), permita quando pedir. Pra celular acessar
via LAN, aceite o prompt de "Rede Privada" na primeira execução.
