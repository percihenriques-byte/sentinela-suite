"""Servico base do modulo Seguranca — M0: auditoria + fontes com consentimento.

Ver ESPEC-SEGURANCA.md. Este arquivo cresce nos marcos seguintes (ativos em M1,
correlacao em M2...); em M0 entra o alicerce que tudo mais usa:

* trilha de auditoria (`registrar_auditoria`) — toda acao sensivel do modulo
  passa por aqui;
* seed idempotente das fontes conhecidas, TODAS desligadas exceto a local
  (`eventos_locais`), cada uma com a descricao exata do que sai da maquina.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlmodel import Session, select

from app.models.secintel import SecAuditoria, SecFonte, SecNivelAutorizacao


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---- auditoria ------------------------------------------------------------

def registrar_auditoria(
    session: Session,
    workspace_id: UUID,
    user_id: UUID,
    acao: str,
    detalhe: Optional[dict] = None,
) -> SecAuditoria:
    """Grava uma linha de auditoria. `detalhe` e minimizado pelo chamador:
    nunca passe valores sensiveis aqui — ids e rotulos bastam."""
    linha = SecAuditoria(
        workspace_id=workspace_id,
        user_id=user_id,
        acao=acao,
        detalhe=json.dumps(detalhe, ensure_ascii=False) if detalhe else None,
        ts=_now(),
    )
    session.add(linha)
    session.commit()
    session.refresh(linha)
    return linha


def listar_auditoria(
    session: Session, workspace_id: UUID, limit: int = 50, offset: int = 0
) -> list[SecAuditoria]:
    return list(
        session.exec(
            select(SecAuditoria)
            .where(
                SecAuditoria.workspace_id == workspace_id,
                SecAuditoria.deleted_at.is_(None),
            )
            .order_by(SecAuditoria.ts.desc())
            .offset(offset)
            .limit(min(limit, 200))
        )
    )


# ---- fontes ---------------------------------------------------------------

# Fonte conhecida = adapter existente ou planejado no ESPEC (secao 10). A
# descricao_egresso e o contrato com o usuario: e mostrada na UX ANTES de
# ligar e diz exatamente o que sai da maquina.
FONTES_CONHECIDAS: list[dict] = [
    {
        "nome": "eventos_locais",
        "habilitada": True,  # 100% local: nada sai da maquina
        "requer_nivel": SecNivelAutorizacao.declarado,
        "descricao_egresso": (
            "Nada sai da maquina. Analisa apenas eventos do proprio app: "
            "logins do painel, trava de PIN, token de ingestao e limites de "
            "requisicao."
        ),
    },
    {
        "nome": "hibp",
        "habilitada": False,
        "requer_nivel": SecNivelAutorizacao.declarado,
        "descricao_egresso": (
            "Envia o e-mail monitorado a API oficial do Have I Been Pwned "
            "para saber se apareceu em vazamentos. Senhas NUNCA sao enviadas: "
            "a checagem de senha usa k-anonymity (apenas os 5 primeiros "
            "caracteres do hash SHA-1 saem da maquina)."
        ),
    },
    {
        "nome": "github_secrets",
        "habilitada": False,
        "requer_nivel": SecNivelAutorizacao.verificado,
        "descricao_egresso": (
            "Usa o seu token GitHub somente-leitura para listar e clonar os "
            "SEUS repositorios e procurar segredos expostos (atual e "
            "historico). Sai da maquina: o nome dos seus repositorios, ao "
            "GitHub. O conteudo e analisado localmente."
        ),
    },
    {
        "nome": "ct",
        "habilitada": False,
        "requer_nivel": SecNivelAutorizacao.verificado,
        "descricao_egresso": (
            "Consulta os logs publicos de Certificate Transparency (crt.sh) "
            "pelos SEUS dominios verificados, para detectar certificados e "
            "subdominios inesperados. Sai da maquina: o nome do dominio."
        ),
    },
]


def garantir_fontes(session: Session) -> list[SecFonte]:
    """Seed idempotente: cria as fontes conhecidas que faltarem, nunca mexe em
    consentimento ja dado (habilitada/consentida_* de linha existente ficam
    como estao)."""
    existentes = {
        f.nome: f
        for f in session.exec(select(SecFonte).where(SecFonte.deleted_at.is_(None)))
    }
    criadas = False
    for spec in FONTES_CONHECIDAS:
        if spec["nome"] in existentes:
            continue
        session.add(SecFonte(**spec))
        criadas = True
    if criadas:
        session.commit()
    return list(
        session.exec(
            select(SecFonte).where(SecFonte.deleted_at.is_(None)).order_by(SecFonte.nome)
        )
    )
