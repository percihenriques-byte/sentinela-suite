"""Fontes de threat intelligence (ESPEC-SEGURANCA.md secao 10).

Contrato: NENHUMA fonte desligada faz chamada de rede. O runner checa o
consentimento (SecFonte.habilitada) ANTES de tocar qualquer adapter. O acesso
a rede passa por um `http` injetavel; o default e um SENTINELA que LEVANTA
excecao — assim, em teste, qualquer request que escape sem consentimento
explode na hora (test_secintel_consentimento).

Adapter = modulo com:
    NOME: str
    REQUER_NIVEL: SecNivelAutorizacao
    def consultar(assets: list[AssetCtx], http) -> list[AchadoBruto]
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional
from uuid import UUID

from sqlmodel import Session, select

from app.core import crypto
from app.models.secintel import (
    SecAchado,
    SecAchadoStatus,
    SecAsset,
    SecClassificacao,
    SecFonte,
    SecFonteEstado,
    SecNivelAutorizacao,
    SecSeveridade,
    SecTipoExposicao,
)
from app.services import secintel_score as score_engine
from app.services.secintel_fontes import fonte_ct, fonte_github, fonte_hibp


@dataclass
class AssetCtx:
    id: UUID
    tipo: str
    identificador: str          # em claro, so em memoria durante a consulta
    nivel: SecNivelAutorizacao


@dataclass
class AchadoBruto:
    asset_id: Optional[UUID]
    tipo_exposicao: SecTipoExposicao
    classificacao: SecClassificacao
    confianca: float
    indicador_mascarado: str
    evidencia_resumo: str
    fingerprint: str
    exposto_em_estimado: Optional[datetime] = None
    motivo_fp: Optional[str] = None


ADAPTERS = {m.NOME: m for m in (fonte_hibp, fonte_ct, fonte_github)}


def _sentinela_http(*_a, **_k):
    raise RuntimeError(
        "secintel: tentativa de acesso a rede SEM consentimento — o runner "
        "deveria ter barrado a fonte desligada antes de chegar aqui."
    )


def _sev_de_classificacao(c: SecClassificacao) -> SecSeveridade:
    conf = score_engine.C_POR_CLASSIFICACAO[c]
    _, sev = score_engine.calcular(
        p=score_engine.P_FORTE, impacto=1.0, confianca=conf, idade_dias=0.0,
        confirmado=(c == SecClassificacao.confirmed),
    )
    return sev


def _assets_elegiveis(session: Session, workspace_id: UUID, requer_nivel: SecNivelAutorizacao,
                      tipos: set[str]) -> list[AssetCtx]:
    q = select(SecAsset).where(
        SecAsset.workspace_id == workspace_id,
        SecAsset.deleted_at.is_(None),
        SecAsset.ativo.is_(True),
        SecAsset.tipo.in_(tipos),
    )
    out = []
    for a in session.exec(q):
        if requer_nivel == SecNivelAutorizacao.verificado and a.nivel_autorizacao != SecNivelAutorizacao.verificado:
            continue
        out.append(AssetCtx(
            id=a.id, tipo=a.tipo.value,
            identificador=crypto.decrypt(a.identificador_enc), nivel=a.nivel_autorizacao,
        ))
    return out


def executar_exposicao(
    session: Session, workspace_id: UUID, http: Optional[Callable] = None,
) -> list[SecAchado]:
    """Roda TODAS as fontes de exposicao HABILITADAS sobre os ativos elegiveis.
    Fonte desligada e pulada — nunca chamada. Dedupe por fingerprint."""
    http = http or _sentinela_http
    tocados: list[SecAchado] = []
    fontes = {f.nome: f for f in session.exec(select(SecFonte).where(SecFonte.deleted_at.is_(None)))}

    for nome, adapter in ADAPTERS.items():
        fonte = fontes.get(nome)
        if not fonte or not fonte.habilitada:
            continue  # SEM consentimento -> nao toca a fonte
        assets = _assets_elegiveis(session, workspace_id, adapter.REQUER_NIVEL, adapter.TIPOS_ATIVO)
        if not assets:
            continue
        try:
            brutos = adapter.consultar(assets, http)
            fonte.estado = SecFonteEstado.ok
            fonte.erro_msg = None
        except Exception as e:  # best-effort: uma fonte com erro nao derruba as outras
            fonte.estado = SecFonteEstado.erro
            fonte.erro_msg = str(e)[:200]
            brutos = []
        fonte.ultima_consulta = datetime.now(timezone.utc)
        session.add(fonte)
        session.commit()

        for b in brutos:
            if b.classificacao == SecClassificacao.false_positive:
                continue  # FP nao vira achado ativo
            tocados.append(_upsert_achado(session, workspace_id, nome, b))
    return tocados


def _upsert_achado(session, workspace_id, fonte_nome, b: AchadoBruto) -> SecAchado:
    existente = session.exec(
        select(SecAchado).where(
            SecAchado.workspace_id == workspace_id,
            SecAchado.fingerprint == b.fingerprint,
            SecAchado.deleted_at.is_(None),
        )
    ).first()
    sev = _sev_de_classificacao(b.classificacao)
    if existente:
        existente.confianca = b.confianca
        existente.severidade = sev
        # Exposicao marcada como RESOLVIDA que reaparece numa varredura futura
        # REABRE: se ela ainda esta la, nao foi resolvida de verdade — deixar o
        # status antigo tornaria a recorrencia invisivel. (Falso-positivo NAO
        # reabre: a decisao humana com motivo prevalece.)
        if existente.status == SecAchadoStatus.resolvido:
            existente.status = SecAchadoStatus.novo
            existente.descoberto_em = datetime.now(timezone.utc)
            existente.evidencia_resumo = (
                f"{b.evidencia_resumo} — REAPARECEU apos ter sido marcada como resolvida"
            )
        session.add(existente)
        session.commit()
        session.refresh(existente)
        return existente
    achado = SecAchado(
        workspace_id=workspace_id, asset_id=b.asset_id, fonte=fonte_nome,
        tipo_exposicao=b.tipo_exposicao, classificacao=b.classificacao,
        confianca=b.confianca, severidade=sev,
        indicador_mascarado=b.indicador_mascarado, evidencia_resumo=b.evidencia_resumo,
        fingerprint=b.fingerprint, descoberto_em=datetime.now(timezone.utc),
        exposto_em_estimado=b.exposto_em_estimado, status=SecAchadoStatus.novo,
        motivo_fp=b.motivo_fp,
    )
    session.add(achado)
    session.commit()
    session.refresh(achado)
    return achado
