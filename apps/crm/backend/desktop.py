"""
VisiQuost desktop launcher.

Roda uvicorn em thread background e abre uma janela pywebview (WebView2 no
Windows) apontando para 127.0.0.1:PORT. Ao fechar a janela, para o servidor.

Por padrao uvicorn ouve SO em 127.0.0.1. O painel do responsavel guarda o
historico de navegacao de uma crianca, decifrado na leitura; expor isso a toda
a rede Wi-Fi por conveniencia nao vale o risco (em rede de predio, escola ou
cafe, "a rede local" inclui estranhos).

Quem realmente quiser abrir no celular liga SENTINELA_BIND_LAN=1, ciente de
que passa a depender so da senha do responsavel.
"""
from __future__ import annotations

import socket
import sys
import threading
import time
from urllib.request import urlopen
from urllib.error import URLError

import uvicorn  # type: ignore
import webview  # type: ignore

import os

PORT = 8000
HOST_LOCAL = "127.0.0.1"
HOST_LAN = "0.0.0.0"


def bind_host() -> str:
    """127.0.0.1 por padrao; 0.0.0.0 so com opt-in explicito."""
    return HOST_LAN if os.environ.get("SENTINELA_BIND_LAN") == "1" else HOST_LOCAL


def wait_for_health(url: str, timeout_s: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=1) as r:
                if r.status == 200:
                    return True
        except (URLError, ConnectionError, OSError):
            pass
        time.sleep(0.2)
    return False


def get_lan_ip() -> str | None:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


def run_server() -> None:
    config = uvicorn.Config(
        "app.main:app",
        host=bind_host(),
        port=PORT,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    server.run()


def main() -> int:
    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    healthz = f"http://{HOST_LOCAL}:{PORT}/healthz"
    if not wait_for_health(healthz):
        print("ERRO: servidor nao ficou pronto em 30s.", file=sys.stderr)
        return 1

    lan = get_lan_ip()
    title = "VisiQuost"
    if lan and lan != HOST_LOCAL:
        title = f"VisiQuost — celular: http://{lan}:{PORT}/"

    webview.create_window(
        title,
        f"http://{HOST_LOCAL}:{PORT}/",
        width=1280,
        height=820,
        min_size=(900, 600),
        confirm_close=False,
    )
    # gui='edgechromium' garante WebView2 (moderno) no Windows
    webview.start(gui="edgechromium")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
