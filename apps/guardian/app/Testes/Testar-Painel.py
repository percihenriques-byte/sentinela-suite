"""E2E do painel do responsavel dentro da SPA da suite.

Sobe um servidor num banco temporario, semeia eventos pela API de ingestao,
entra no app pelo navegador e confere que a pagina Sentinela renderiza os
numeros, a lista, os temas e a configuracao — sem erro de console.

Uso (a partir da raiz do monorepo):
    apps/crm/backend/.venv/Scripts/python.exe apps/guardian/app/Testes/Testar-Painel.py
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
BACKEND = RAIZ / "apps" / "crm" / "backend"
SAIDA = BACKEND / "screenshots"

falhas: list[str] = []
oks: list[str] = []


def checar(nome: str, cond: bool, detalhe: str = "") -> None:
    (oks if cond else falhas).append(nome)
    print(f"  [{'OK  ' if cond else 'FALHA'}] {nome} {'' if cond else detalhe}")


def porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def api(base, rota, dados=None, token=None, cabecalhos=None):
    req = urllib.request.Request(base + rota, method="POST" if dados is not None else "GET")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for k, v in (cabecalhos or {}).items():
        req.add_header(k, v)
    corpo = json.dumps(dados).encode() if dados is not None else None
    with urllib.request.urlopen(req, corpo, timeout=10) as r:
        return json.loads(r.read().decode() or "{}")


def _diagnostico(log_servidor, servidor) -> None:
    """Mostra por que o servidor nao subiu, em vez de so dizer que nao subiu."""
    print("  [FALHA] servidor nao subiu")
    print(f"  codigo de saida: {servidor.poll()}")
    try:
        texto = log_servidor.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        texto = ""
    if texto:
        print("  --- saida do servidor ---")
        for linha in texto.splitlines()[-25:]:
            print(f"    {linha}")
    else:
        print("  (servidor nao escreveu nada — provavelmente nem chegou a iniciar)")


def main() -> int:
    from playwright.sync_api import sync_playwright

    porta = porta_livre()
    base = f"http://127.0.0.1:{porta}"
    tmp = Path(tempfile.mkdtemp(prefix="sentinela-painel-"))
    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite:///{(tmp / 'teste.db').as_posix()}"
    env["APP_SECRET_KEY"] = "teste-painel-secret"
    env["FIELD_ENCRYPTION_KEY"] = "teste-painel-encryption"
    env["RATE_LIMIT_ENABLED"] = "false"

    # Saida do servidor em arquivo: sem isso, "nao subiu" nao diz por que.
    log_servidor = tmp / "servidor.log"
    handle_log = open(log_servidor, "w", encoding="utf-8", errors="replace")
    servidor = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(porta)],
        cwd=str(BACKEND), env=env, stdout=handle_log, stderr=subprocess.STDOUT,
    )
    email, senha = "mae@exemplo.com", "senha-de-teste-123"
    try:
        limite = time.time() + 90
        pronto = False
        while time.time() < limite and not pronto:
            try:
                with urllib.request.urlopen(base + "/healthz", timeout=1) as r:
                    pronto = r.status == 200
            except (urllib.error.URLError, OSError):
                time.sleep(0.3)
        if not pronto:
            _diagnostico(log_servidor, servidor)
            return 1

        jwt = api(base, "/api/v1/auth/register", {
            "email": email, "password": senha, "full_name": "Mae", "workspace_name": "Casa",
        })["access_token"]
        ingest = api(base, "/api/v1/sentinela/config", token=jwt)["token_ingestao"]

        agora = datetime.now(timezone.utc)
        eventos = [
            {"busca": "filhotes de golden retriever", "origem": "google", "dispositivo": "pc-da-sala",
             "bloqueado": False, "ocorrido_em": (agora - timedelta(minutes=40)).isoformat()},
            {"busca": "exercicios de matematica 9 ano", "origem": "google", "dispositivo": "pc-da-sala",
             "bloqueado": False, "ocorrido_em": (agora - timedelta(minutes=30)).isoformat()},
            {"busca": "jogo do tigrinho", "origem": "google", "dispositivo": "pc-da-sala", "tema": "Apostas",
             "confianca": 1.0, "bloqueado": True, "ocorrido_em": (agora - timedelta(minutes=20)).isoformat()},
            {"busca": "cassino online", "origem": "bing", "dispositivo": "tablet", "tema": "Apostas",
             "confianca": 1.0, "bloqueado": True, "ocorrido_em": (agora - timedelta(minutes=12)).isoformat()},
            {"busca": "como burlar o filtro da escola", "origem": "google", "dispositivo": "tablet",
             "tema": "Burlar protecao", "confianca": 1.0, "bloqueado": True,
             "ocorrido_em": (agora - timedelta(minutes=6)).isoformat()},
        ]
        api(base, "/api/v1/sentinela/eventos", {"eventos": eventos},
            cabecalhos={"X-Sentinela-Token": ingest})
        checar("eventos semeados pela API de ingestao",
               api(base, "/api/v1/sentinela/eventos", token=jwt)["total"] == 5)

        erros: list[str] = []
        with sync_playwright() as pw:
            nav = pw.chromium.launch(headless=True)
            # locale fixo: o app detecta o idioma do navegador, e o runner do CI
            # esta em ingles. Sem isto o teste passava aqui e falhava la, culpando
            # o produto por acertar. A traducao para EN e conferida adiante, de
            # proposito, trocando no seletor de idioma.
            ctx = nav.new_context(viewport={"width": 1440, "height": 950}, locale="pt-BR")
            pag = ctx.new_page()
            pag.on("pageerror", lambda e: erros.append(f"pageerror: {e}"))
            pag.on("console", lambda m: erros.append(f"console.error: {m.text}") if m.type == "error" else None)

            pag.goto(base, wait_until="networkidle")

            # --- identidade: o app se apresenta como Sentinela, nao como o CRM ---
            checar("titulo da pagina e do Sentinela", "Sentinela" in pag.title(), f"-> {pag.title()!r}")
            checar("marca da tela de entrada e Sentinela",
                   pag.locator(".auth-logo .brand-name").inner_text().strip() == "Sentinela",
                   f"-> {pag.locator('.auth-logo .brand-name').inner_text()!r}")
            manchete = pag.locator(".auth-headline h1").inner_text()
            checar("manchete fala de proteção antes de trabalho",
                   "protegida" in manchete.lower(), f"-> {manchete!r}")
            checar("entrada abre em português com locale pt-BR",
                   "protected" not in manchete.lower(), f"-> {manchete!r}")

            pag.fill('input[type="email"]', email)
            pag.fill('input[type="password"]', senha)
            pag.click('button[type="submit"]')
            pag.wait_for_selector(".app-view:not(.hidden)", timeout=15000)
            pag.wait_for_timeout(1200)

            checar("marca do menu lateral e Sentinela",
                   pag.locator(".brand-row .brand").inner_text().strip() == "Sentinela")
            checar("Sentinela e o primeiro item do menu",
                   pag.locator(".nav-item").first.get_attribute("data-page") == "sentinela",
                   f"-> {pag.locator('.nav-item').first.get_attribute('data-page')!r}")
            checar("menu separa o modulo de CRM",
                   pag.locator(".nav-section").inner_text().strip().upper() == "CRM")
            checar("primeiro acesso abre no Sentinela",
                   not pag.locator("#page-sentinela").evaluate("e => e.classList.contains('hidden')"))

            # Sem PIN a trava parental nao existe. Como o app ja abre no
            # Sentinela, o pedido de PIN aparece aqui, antes de qualquer clique
            # (achado A3 da auditoria: aviso em cinza que ninguem le nao protege).
            pag.wait_for_timeout(900)
            modal_pin = pag.locator("#modal:not(.hidden)")
            checar("primeira visita pede o PIN do responsavel", modal_pin.count() == 1,
                   "-> nao pediu")
            if modal_pin.count():
                checar("o pedido de PIN diz do que se trata",
                       "PIN" in pag.locator("#modal-title").inner_text(),
                       f"-> {pag.locator('#modal-title').inner_text()!r}")
                pag.click("#modal-cancel")
                pag.wait_for_timeout(400)

            alvo = '.nav-item[data-page="sentinela"]'
            checar("item Sentinela existe no menu", pag.locator(alvo).count() == 1)
            pag.click(alvo)
            pag.wait_for_selector("#page-sentinela:not(.hidden)", timeout=10000)
            pag.wait_for_timeout(1200)

            kpis = pag.locator("#sn-kpis .kpi")
            checar("painel mostra os 4 indicadores", kpis.count() == 4, f"-> {kpis.count()}")
            checar("contagem de bloqueadas correta",
                   kpis.nth(0).locator(".value").inner_text().strip() == "3",
                   f"-> {kpis.nth(0).inner_text()!r}")
            checar("contagem de observadas correta",
                   kpis.nth(1).locator(".value").inner_text().strip() == "5")
            checar("dispositivos listados",
                   "pc-da-sala" in kpis.nth(2).inner_text() and "tablet" in kpis.nth(2).inner_text(),
                   f"-> {kpis.nth(2).inner_text()!r}")

            evs = pag.locator("#sn-lista .sn-ev")
            checar("lista mostra as 5 tentativas", evs.count() == 5, f"-> {evs.count()}")
            checar("a busca aparece decifrada no painel",
                   "tigrinho" in pag.locator("#sn-lista").inner_text())
            checar("bloqueadas ficam marcadas", pag.locator("#sn-lista .sn-ev.bloq").count() == 3)

            checar("temas mais barrados aparecem",
                   "Apostas" in pag.locator("#sn-temas").inner_text())

            pag.check("#sn-so-bloq")
            pag.wait_for_timeout(900)
            checar("filtro 'so bloqueadas' funciona",
                   pag.locator("#sn-lista .sn-ev").count() == 3,
                   f"-> {pag.locator('#sn-lista .sn-ev').count()}")
            pag.uncheck("#sn-so-bloq")
            pag.wait_for_timeout(900)

            checar("configuracao carregou", pag.locator("#sn-sens").input_value() == "media")
            pag.select_option("#sn-sens", "alta")
            pag.wait_for_timeout(900)
            checar("mudar sensibilidade persiste na API",
                   api(base, "/api/v1/sentinela/config", token=jwt)["sensibilidade"] == "alta")

            checar("aviso de PIN ausente aparece",
                   "sem PIN" in pag.locator("#sn-pin-estado").inner_text())

            pag.click("#sn-conectar")
            pag.wait_for_selector("#sn-token-val", timeout=5000)
            checar("modal de conectar mostra o token",
                   pag.locator("#sn-token-val").inner_text().strip() == ingest)
            pag.click("#modal-cancel")

            SAIDA.mkdir(exist_ok=True)
            pag.screenshot(path=str(SAIDA / "10_sentinela.png"))

            # --- tema claro: a marca tem de continuar legivel ---
            pag.evaluate("document.documentElement.setAttribute('data-theme','light')")
            pag.wait_for_timeout(400)
            fundo = pag.evaluate("getComputedStyle(document.body).backgroundColor")
            checar("tema claro troca o fundo", fundo not in ("rgb(11, 18, 32)", "rgba(0, 0, 0, 0)"), f"-> {fundo}")
            primaria = pag.evaluate(
                "getComputedStyle(document.documentElement).getPropertyValue('--primary').trim()")
            checar("tema claro usa o teal escuro da marca", primaria == "#0ea5a0", f"-> {primaria!r}")
            pag.screenshot(path=str(SAIDA / "11_sentinela_claro.png"))
            pag.evaluate("document.documentElement.setAttribute('data-theme','dark')")

            # --- mobile: nada pode vazar na horizontal ---
            pag.set_viewport_size({"width": 390, "height": 844})
            pag.wait_for_timeout(500)
            vazamento = pag.evaluate(
                "document.documentElement.scrollWidth - document.documentElement.clientWidth")
            checar("sem rolagem horizontal no celular", vazamento <= 1, f"-> vazou {vazamento}px")
            checar("colunas empilham no celular",
                   pag.evaluate("getComputedStyle(document.querySelector('.sn-cols')).gridTemplateColumns")
                   .count(" ") == 0, "-> continuou em 2 colunas")
            pag.screenshot(path=str(SAIDA / "12_sentinela_mobile.png"), full_page=True)
            pag.set_viewport_size({"width": 1440, "height": 950})

            # --- o app lembra a secao: quem usa o CRM nao cai no Sentinela sempre ---
            pag.click('.nav-item[data-page="dashboard"]')
            pag.wait_for_timeout(600)
            pag.reload(wait_until="networkidle")
            pag.wait_for_selector(".app-view:not(.hidden)", timeout=15000)
            pag.wait_for_timeout(1500)
            checar("app volta na ultima secao usada",
                   not pag.locator("#page-dashboard").evaluate("e => e.classList.contains('hidden')"),
                   "-> nao lembrou a secao")

            # --- tela de entrada em ingles ---
            pag.goto(base + "?lang=en", wait_until="networkidle")
            pag.evaluate("localStorage.clear()")
            pag.reload(wait_until="networkidle")
            pag.select_option("#auth-lang-select", "en")
            pag.wait_for_timeout(500)
            manchete_en = pag.locator(".auth-headline h1").inner_text()
            checar("manchete traduz para ingles",
                   "protected" in manchete_en.lower(), f"-> {manchete_en!r}")
            checar("cartoes do Sentinela traduzem",
                   "switched off" in pag.locator(".auth-cards").inner_text().lower(),
                   f"-> {pag.locator('.auth-cards').inner_text()[:80]!r}")
            pag.screenshot(path=str(SAIDA / "13_entrada.png"))

            print(f"  screenshots: {SAIDA}")
            ctx.close()
            nav.close()

        checar("nenhum erro de console/JS", not erros, f"-> {erros[:3]}")
    finally:
        servidor.terminate()
        try:
            servidor.wait(timeout=10)
        except subprocess.TimeoutExpired:
            servidor.kill()

    print("\n  " + "-" * 42)
    print(f"  RESULTADO: {len(oks)} passaram, {len(falhas)} falharam\n")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
