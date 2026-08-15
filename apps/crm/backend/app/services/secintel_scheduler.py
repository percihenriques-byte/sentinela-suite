"""Laços de monitoramento continuo do modulo Seguranca (ESPEC secao 6, Fase 10).

Mesmo padrao dos schedulers existentes (retencao_scheduler): laços asyncio
best-effort — excecao e logada e engolida, nunca derruba a API. Tres laços:

    correlacao (5 min)  — roda as regras sobre os eventos recentes de cada
                          workspace; cria/atualiza incidentes. Sem rede.
    exposicao  (24 h)   — roda as fontes HABILITADAS sobre os ativos. Fonte
                          desligada nunca e chamada (trava de consentimento).
    higiene    (24 h)   — aplica retencoes e fecha incidentes recuperados. Sem
                          rede.

Todos com dedupe por fingerprint (nunca duplicam incidente/achado).
"""
from __future__ import annotations

import asyncio
import logging

from app.db.session import engine
from sqlmodel import Session

from app.services import secintel_service as svc

logger = logging.getLogger("jarvis.secintel")

INTERVALO_CORRELACAO_S = 5 * 60
INTERVALO_EXPOSICAO_S = 24 * 60 * 60
INTERVALO_HIGIENE_S = 24 * 60 * 60


def _http_real(url: str, headers: dict | None = None):
    """Cliente HTTP real, importado sob demanda. So e chamado por uma fonte
    HABILITADA (o runner barra as desligadas antes de chegar aqui)."""
    import httpx

    return httpx.get(url, headers=headers or {}, timeout=20.0, follow_redirects=True)


# leitura de repositorio para o github_secrets: tarball da API do GitHub, com
# token opcional (repos privados), limite de tamanho por arquivo e allowlist de
# extensoes de texto (nao adianta varrer binario atras de secret).
_GH_TARBALL = "https://api.github.com/repos/{repo}/tarball"
_MAX_ARQUIVO_BYTES = 512 * 1024          # 512 KB por arquivo
_MAX_ARQUIVOS = 2000
_EXT_TEXTO = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yml", ".yaml", ".env",
    ".sh", ".ps1", ".rb", ".go", ".java", ".php", ".txt", ".cfg", ".ini",
    ".toml", ".xml", ".properties", ".tf", ".conf", ".md",
}


def _repo_files_github(asset, credencial=None):
    """transporte "repo_files": baixa o tarball do repo `owner/nome` e devolve
    [(caminho, texto)] dos arquivos de texto dentro dos limites. Importado sob
    demanda; so chamado por fonte HABILITADA e repo `verificado`."""
    import io
    import tarfile

    import httpx

    headers = {"User-Agent": "Sentinela-Seguranca", "Accept": "application/vnd.github+json"}
    if credencial:
        headers["Authorization"] = f"Bearer {credencial}"
    resp = httpx.get(_GH_TARBALL.format(repo=asset.identificador),
                     headers=headers, timeout=30.0, follow_redirects=True)
    if resp.status_code != 200:
        raise RuntimeError(f"GitHub respondeu {resp.status_code} para {asset.identificador}")

    arquivos = []
    with tarfile.open(fileobj=io.BytesIO(resp.content), mode="r:gz") as tar:
        for membro in tar:
            if not membro.isfile() or membro.size > _MAX_ARQUIVO_BYTES:
                continue
            # o tarball prefixa com "owner-repo-sha/"; tira o primeiro componente
            caminho = membro.name.split("/", 1)[-1]
            ext = caminho[caminho.rfind("."):].lower() if "." in caminho else ""
            if ext not in _EXT_TEXTO:
                continue
            f = tar.extractfile(membro)
            if f is None:
                continue
            try:
                texto = f.read().decode("utf-8", errors="replace")
            except Exception:
                continue
            arquivos.append((caminho, texto))
            if len(arquivos) >= _MAX_ARQUIVOS:
                break
    return arquivos


def _transportes_reais() -> dict:
    return {"http_url": _http_real, "repo_files": _repo_files_github}


# ---- passos sincronos (testaveis isoladamente) ----------------------------

def ciclo_correlacao_agora() -> int:
    total = 0
    with Session(engine) as session:
        for ws_id in svc.workspaces_ativos(session):
            total += len(svc.correlacionar(session, ws_id))
    return total


def ciclo_exposicao_agora(transportes=None) -> int:
    total = 0
    tr = transportes or _transportes_reais()
    with Session(engine) as session:
        for ws_id in svc.workspaces_ativos(session):
            total += len(svc.rodar_exposicao(session, ws_id, transportes=tr))
    return total


def ciclo_higiene_agora() -> dict:
    with Session(engine) as session:
        return svc.aplicar_higiene(session)


# ---- laços assincronos ----------------------------------------------------

async def _laco(stop_event: asyncio.Event, passo, intervalo_s: str, rotulo: str) -> None:
    while not stop_event.is_set():
        try:
            await asyncio.to_thread(passo)
        except Exception:
            logger.exception("secintel_%s_falhou", rotulo)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=intervalo_s)
        except asyncio.TimeoutError:
            continue


async def run_secintel_scheduler(stop_event: asyncio.Event) -> None:
    await asyncio.gather(
        _laco(stop_event, ciclo_correlacao_agora, INTERVALO_CORRELACAO_S, "correlacao"),
        _laco(stop_event, ciclo_exposicao_agora, INTERVALO_EXPOSICAO_S, "exposicao"),
        _laco(stop_event, ciclo_higiene_agora, INTERVALO_HIGIENE_S, "higiene"),
    )
