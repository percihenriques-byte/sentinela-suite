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

    return httpx.get(url, headers=headers or {}, timeout=20.0)


# ---- passos sincronos (testaveis isoladamente) ----------------------------

def ciclo_correlacao_agora() -> int:
    total = 0
    with Session(engine) as session:
        for ws_id in svc.workspaces_ativos(session):
            total += len(svc.correlacionar(session, ws_id))
    return total


def ciclo_exposicao_agora(http=None) -> int:
    total = 0
    with Session(engine) as session:
        for ws_id in svc.workspaces_ativos(session):
            total += len(svc.rodar_exposicao(session, ws_id, http=http or _http_real))
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
