"""Purga periodica do registro de supervisao.

Antes a retencao so era aplicada ao final de `POST /sentinela/eventos`. Numa
instalacao que para de receber eventos — crianca de ferias, PC de uso ocasional,
extensao desconectada — nada era purgado nunca, e dado sensivel alem da janela
ficava indefinidamente. Privacidade nao pode depender de haver movimento.

Diferente do backup, este laco roda sempre: a retencao e uma promessa ao
usuario, nao um recurso opcional.

Best-effort igual ao backup: excecao e registrada e engolida, para uma purga
com problema nunca derrubar a API.
"""
from __future__ import annotations

import asyncio
import logging

from sqlmodel import Session

from app.db.session import engine
from app.services import sentinela_service as svc

logger = logging.getLogger("jarvis.retencao")

# A janela padrao e de 90 dias; verificar de 6 em 6 horas e folgado e barato
# (uma contagem indexada por ciclo).
INTERVALO_S = 6 * 60 * 60


def aplicar_agora() -> int:
    with Session(engine) as session:
        return svc.aplicar_retencao(session)


async def run_retention_scheduler(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            removidos = await asyncio.to_thread(aplicar_agora)
            if removidos:
                logger.info("retencao_purgou eventos=%d", removidos)
        except Exception:
            logger.exception("retencao_falhou")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=INTERVALO_S)
        except asyncio.TimeoutError:
            continue
