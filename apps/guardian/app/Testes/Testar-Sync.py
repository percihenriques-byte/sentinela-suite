"""E2E: extensao do Sentinela -> painel local da suite.

Sobe um servidor da suite num banco temporario, carrega a extensao real no
Chromium, faz uma busca impropria numa pagina servida por esse servidor e
verifica que:

  1. o content script bloqueou a busca (IA local);
  2. o evento chegou na API pelo service worker;
  3. o texto da busca esta cifrado no banco;
  4. sem token valido a ingestao e recusada e a fila NAO se perde.

Nada sai da maquina: servidor e navegador falam so com 127.0.0.1.

Uso (a partir da raiz do monorepo):
    apps/crm/backend/.venv/Scripts/python.exe apps/guardian/app/Testes/Testar-Sync.py
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]          # .../sentinela-suite
EXT = RAIZ / "apps" / "guardian" / "app" / "extensao"
BACKEND = RAIZ / "apps" / "crm" / "backend"

falhas: list[str] = []
oks: list[str] = []


def checar(nome: str, condicao: bool, detalhe: str = "") -> None:
    if condicao:
        oks.append(nome)
        print(f"  [OK]   {nome}")
    else:
        falhas.append(nome)
        print(f"  [FALHA] {nome} {detalhe}")


def porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def esperar_servidor(base: str, segundos: float = 90.0) -> bool:
    limite = time.time() + segundos
    while time.time() < limite:
        try:
            with urllib.request.urlopen(base + "/healthz", timeout=1) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            time.sleep(0.3)
    return False


def api(base: str, rota: str, dados=None, token=None, metodo=None):
    import json

    req = urllib.request.Request(base + rota, method=metodo or ("POST" if dados is not None else "GET"))
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    corpo = json.dumps(dados).encode() if dados is not None else None
    with urllib.request.urlopen(req, corpo, timeout=10) as r:
        return json.loads(r.read().decode() or "{}")


def powershell(script: str) -> tuple[int, str]:
    """Roda um trecho de PowerShell no modo simulacao (nada toca o sistema real)."""
    completo = "$ErrorActionPreference='Stop'; $env:SENTINELA_SIMULAR='1'; " + script
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", completo],
        capture_output=True, text=True, timeout=120,
    )
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def testar_ponte_powershell(base: str, token: str, jwt: str) -> None:
    """O app Windows tambem entrega o que classifica ao painel."""
    app = RAIZ / "apps" / "guardian" / "app"
    carregar = (
        f". '{app / 'Sentinela-Core.ps1'}'; . '{app / 'Sentinela-Classificador.ps1'}'; "
        f". '{app / 'Sentinela-Supervisao.ps1'}'; . '{app / 'Sentinela-Ponte.ps1'}'; "
    )
    # Comeca de uma pasta de simulacao limpa: sobra de execucao anterior
    # falsearia a contagem.
    powershell("Remove-Item -Recurse -Force (Join-Path $env:TEMP 'SentinelaSim') -ErrorAction SilentlyContinue")

    cod, saida = powershell(
        carregar + "try { Set-PainelConfig -Url 'http://exemplo.com' -Token 'x' -Ligado $true | Out-Null; "
        "'ACEITOU' } catch { 'RECUSOU' }"
    )
    checar("ponte PS recusa painel fora do loopback", "RECUSOU" in saida, f"-> {saida.strip()[:120]}")

    cod, saida = powershell(
        carregar + f"Set-PainelConfig -Url '{base}' -Token '{token}' -Dispositivo 'pc-powershell' -Ligado $true | Out-Null; "
        "Add-SupervisaoRegistro -Texto 'jogo do tigrinho' -Origem 'app' | Out-Null; 'FEITO'"
    )
    checar("app PowerShell registrou e enviou", cod == 0 and "FEITO" in saida, f"-> {saida.strip()[:200]}")

    eventos = api(base, "/api/v1/sentinela/eventos?dispositivo=pc-powershell", token=jwt)
    checar("evento do app PowerShell chegou ao painel", eventos["total"] == 1, f"-> {eventos['total']}")
    if eventos["total"]:
        ev = eventos["items"][0]
        checar("classificacao do app veio junto", ev["bloqueado"] and ev["tema"], f"-> {ev}")
        checar("busca do app aparece decifrada", ev["busca"] == "jogo do tigrinho", f"-> {ev['busca']!r}")

    # Envio em massa do historico (primeira conexao / painel que ficou fora).
    cod, saida = powershell(carregar + "Sync-SupervisaoComPainel")
    total = api(base, "/api/v1/sentinela/eventos?dispositivo=pc-powershell", token=jwt)["total"]
    checar("EnviarTudo reenvia o historico acumulado", total == 2, f"-> {total} (saida: {saida.strip()[:120]})")

    cod, saida = powershell(carregar + "Set-PainelConfig -Ligado $false | Out-Null; "
                            "Add-SupervisaoRegistro -Texto 'cassino online' -Origem 'app' | Out-Null; 'FEITO'")
    total2 = api(base, "/api/v1/sentinela/eventos?dispositivo=pc-powershell", token=jwt)["total"]
    checar("com a ponte desligada nada e enviado", total2 == total, f"-> {total2}")


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
    tmp = Path(tempfile.mkdtemp(prefix="sentinela-sync-"))
    db = tmp / "teste.db"

    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite:///{db.as_posix()}"
    env["APP_SECRET_KEY"] = "teste-sync-secret"
    env["FIELD_ENCRYPTION_KEY"] = "teste-sync-encryption"
    env["RATE_LIMIT_ENABLED"] = "false"

    print(f"\n  Servidor de teste: {base}  (banco temporario)")
    # A saida do servidor vai para arquivo, nao para DEVNULL: quando ele nao sobe
    # (aconteceu no primeiro CI real), "servidor nao subiu" sozinho nao diz nada.
    log_servidor = tmp / "servidor.log"
    handle_log = open(log_servidor, "w", encoding="utf-8", errors="replace")
    servidor = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(porta)],
        cwd=str(BACKEND), env=env,
        stdout=handle_log, stderr=subprocess.STDOUT,
    )
    udd = tmp / "perfil"
    try:
        if not esperar_servidor(base):
            _diagnostico(log_servidor, servidor)
            return 1

        conta = api(base, "/api/v1/auth/register", {
            "email": "responsavel@exemplo.com", "password": "senha-de-teste-123",
            "full_name": "Responsavel", "workspace_name": "Casa",
        })
        jwt = conta["access_token"]
        token = api(base, "/api/v1/sentinela/config", token=jwt)["token_ingestao"]
        checar("painel gera token de ingestao", bool(token))

        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                str(udd), headless=False,
                args=["--headless=new", f"--load-extension={EXT}", f"--disable-extensions-except={EXT}"],
            )
            try:
                sw = None
                limite = time.time() + 20
                while time.time() < limite and sw is None:
                    sw = ctx.service_workers[0] if ctx.service_workers else None
                    if sw is None:
                        ctx.new_page().goto(base + "/healthz")
                        time.sleep(0.4)
                checar("service worker da extensao carregou", sw is not None)
                if sw is None:
                    return 1

                checar("sync.js foi importado pelo service worker",
                       sw.evaluate("() => !!self.SentinelaSync"))
                checar("sync recusa endereco fora do loopback",
                       sw.evaluate("() => !self.SentinelaSync.ehLoopback('http://exemplo.com')"))

                # --- 1) sem token: ingestao recusada, fila preservada ---
                sw.evaluate(
                    """async ([url]) => {
                        await chrome.storage.local.set({ sentinela_servidor:
                            { url, token: 'token-errado', dispositivo: 'pc-teste', ligado: true } });
                        await chrome.storage.local.set({ sentinela_fila: [] });
                    }""", [base])
                r = sw.evaluate(
                    """async () => {
                        await self.SentinelaSync.enfileirar(
                            { hora: new Date().toISOString(), busca: 'evento perdido?', origem: 'teste' });
                        return await self.SentinelaSync.enviar();
                    }""")
                checar("token invalido e recusado", r.get("erro") == "token", f"-> {r}")
                checar("fila nao e perdida quando o token falha", r.get("restantes") == 1, f"-> {r}")

                # --- 2) token certo: a fila pendente sobe ---
                sw.evaluate(
                    """async ([url, token]) => chrome.storage.local.set({ sentinela_servidor:
                        { url, token, dispositivo: 'pc-teste', ligado: true } })""", [base, token])
                r = sw.evaluate("async () => await self.SentinelaSync.enviar()")
                checar("evento que estava na fila e entregue", r.get("enviados") == 1, f"-> {r}")
                checar("fila fica vazia apos entrega", r.get("restantes") == 0, f"-> {r}")

                lista = api(base, "/api/v1/sentinela/eventos", token=jwt)
                checar("painel recebeu o evento da fila", lista["total"] == 1, f"-> {lista['total']}")
                checar("dispositivo veio junto",
                       lista["items"][0]["dispositivo"] == "pc-teste", f"-> {lista['items'][0]}")

                # --- 3) busca real no navegador, com a extensao agindo ---
                pagina = ctx.new_page()
                pagina.goto(base + "/?q=conteudo+adulto+%2B18", wait_until="domcontentloaded")
                pagina.wait_for_timeout(2500)
                corpo = pagina.content()
                checar("IA local bloqueou a busca impropria", "Conte" in corpo and "bloqueado" in corpo.lower())

                # o envio e assincrono; da um tempo e, se preciso, forca
                limite = time.time() + 10
                total = 1
                while time.time() < limite:
                    total = api(base, "/api/v1/sentinela/eventos", token=jwt)["total"]
                    if total >= 2:
                        break
                    time.sleep(0.5)
                automatico = total >= 2
                if not automatico:  # nao devia precisar; se precisar, o teste avisa
                    sw.evaluate("async () => await self.SentinelaSync.enviar()")
                    total = api(base, "/api/v1/sentinela/eventos", token=jwt)["total"]
                checar("busca do navegador chegou ao painel", total >= 2, f"-> total={total}")
                checar("chegou sozinha (sem forcar sincronizacao)", automatico,
                       "-> so chegou apos flush manual")

                eventos = api(base, "/api/v1/sentinela/eventos", token=jwt)["items"]
                bloqueado = [e for e in eventos if e["bloqueado"]]
                checar("evento chegou marcado como bloqueado", len(bloqueado) >= 1)
                if bloqueado:
                    checar("veredito da IA veio junto (tema)", bool(bloqueado[0]["tema"]), f"-> {bloqueado[0]}")

                resumo = api(base, "/api/v1/sentinela/resumo", token=jwt)
                checar("resumo do painel conta os bloqueios", resumo["bloqueados"] >= 1, f"-> {resumo}")
                checar("resumo lista o dispositivo", "pc-teste" in resumo["dispositivos"], f"-> {resumo['dispositivos']}")
            finally:
                ctx.close()

        # --- 4) a ponte do app PowerShell tambem entrega ao painel ---
        testar_ponte_powershell(base, token, jwt)

        # --- 5) o texto da busca nao pode estar legivel no banco ---
        import sqlite3
        con = sqlite3.connect(str(db))
        cru = " ".join(str(r[0]) for r in con.execute("select busca_enc from sentinelaevent"))
        con.close()
        checar("busca fica cifrada no banco", "adulto" not in cru.lower())
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
