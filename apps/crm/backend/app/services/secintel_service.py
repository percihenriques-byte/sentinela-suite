"""Servico base do modulo Seguranca — M0: auditoria + fontes com consentimento.

Ver ESPEC-SEGURANCA.md. Este arquivo cresce nos marcos seguintes (ativos em M1,
correlacao em M2...); em M0 entra o alicerce que tudo mais usa:

* trilha de auditoria (`registrar_auditoria`) — toda acao sensivel do modulo
  passa por aqui;
* seed idempotente das fontes conhecidas, TODAS desligadas exceto a local
  (`eventos_locais`), cada uma com a descricao exata do que sai da maquina.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.core import crypto
from app.models import User
from app.models.secintel import (
    SecAsset,
    SecAssetTipo,
    SecAuditoria,
    SecFonte,
    SecNivelAutorizacao,
    SecTitular,
)
from app.services import secintel_mascara as mascara


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(valor: str) -> str:
    return hashlib.sha256(valor.strip().lower().encode("utf-8")).hexdigest()


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


# ---- ativos (M1) ----------------------------------------------------------

def criar_asset(
    session: Session,
    workspace_id: UUID,
    user: User,
    tipo: SecAssetTipo,
    identificador: str,
    titular: SecTitular = SecTitular.responsavel,
    fonte_cadastro: str = "manual",
) -> SecAsset:
    """Cadastra um ativo autorizado. Identificador vai cifrado (Fernet) + hash
    (dedupe/busca) + mascarado (listagem). Dedupe por (workspace, tipo, hash):
    recadastrar o mesmo ativo devolve o existente (reativado se arquivado)."""
    identificador = (identificador or "").strip()
    if not identificador:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "identificador vazio")
    h = _hash(identificador)
    existente = session.exec(
        select(SecAsset).where(
            SecAsset.workspace_id == workspace_id,
            SecAsset.tipo == tipo,
            SecAsset.identificador_hash == h,
            SecAsset.deleted_at.is_(None),
        )
    ).first()
    if existente:
        if not existente.ativo:
            existente.ativo = True
            session.add(existente)
            session.commit()
            session.refresh(existente)
        return existente

    nivel, verificado_em = _avaliar_posse(session, user, tipo, identificador)
    asset = SecAsset(
        workspace_id=workspace_id,
        tipo=tipo,
        identificador_enc=crypto.encrypt(identificador),
        identificador_hash=h,
        identificador_mascarado=mascara.mascarar_por_tipo(tipo.value, identificador),
        titular=titular,
        nivel_autorizacao=nivel,
        verificado_em=verificado_em,
        fonte_cadastro=fonte_cadastro,
        ativo=True,
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


def listar_assets(
    session: Session, workspace_id: UUID, incluir_arquivados: bool = False
) -> list[SecAsset]:
    q = select(SecAsset).where(
        SecAsset.workspace_id == workspace_id, SecAsset.deleted_at.is_(None)
    )
    if not incluir_arquivados:
        q = q.where(SecAsset.ativo.is_(True))
    return list(session.exec(q.order_by(SecAsset.created_at.desc())))


def get_asset(session: Session, workspace_id: UUID, asset_id: UUID) -> SecAsset:
    asset = session.get(SecAsset, asset_id)
    if not asset or asset.workspace_id != workspace_id or asset.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ativo nao encontrado")
    return asset


def editar_asset(
    session: Session, workspace_id: UUID, asset_id: UUID, titular: Optional[SecTitular]
) -> SecAsset:
    asset = get_asset(session, workspace_id, asset_id)
    if titular is not None:
        asset.titular = titular
        session.add(asset)
        session.commit()
        session.refresh(asset)
    return asset


def arquivar_asset(session: Session, workspace_id: UUID, asset_id: UUID) -> None:
    asset = get_asset(session, workspace_id, asset_id)
    asset.ativo = False
    session.add(asset)
    session.commit()


def _avaliar_posse(
    session: Session, user: User, tipo: SecAssetTipo, identificador: str
) -> tuple[SecNivelAutorizacao, Optional[datetime]]:
    """Verificacao de posse SEM rede (ESPEC secao 2). Em M1, so o e-mail de
    login do responsavel e auto-verificado. Dominio/repo exigem fontes de rede
    (ct/github), que chegam no M4: ate la ficam `declarado`."""
    if tipo == SecAssetTipo.email and identificador.strip().lower() == user.email.strip().lower():
        return SecNivelAutorizacao.verificado, _now()
    return SecNivelAutorizacao.declarado, None


def verificar_posse(
    session: Session, workspace_id: UUID, user: User, asset_id: UUID
) -> SecAsset:
    """Reavalia a posse de um ativo. Registra `ultima_verificacao`."""
    asset = get_asset(session, workspace_id, asset_id)
    identificador = crypto.decrypt(asset.identificador_enc)
    nivel, verificado_em = _avaliar_posse(session, user, asset.tipo, identificador)
    asset.nivel_autorizacao = nivel
    if verificado_em and asset.verificado_em is None:
        asset.verificado_em = verificado_em
    asset.ultima_verificacao = _now()
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset
