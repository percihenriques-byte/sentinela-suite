"""Payloads do modulo Seguranca."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.models.secintel import (
    SecAssetTipo,
    SecFonteEstado,
    SecNivelAutorizacao,
    SecTitular,
)


# ---- fontes / auditoria (M0) ----

class FonteOut(BaseModel):
    nome: str
    habilitada: bool
    requer_nivel: SecNivelAutorizacao
    descricao_egresso: str
    consentida_em: Optional[datetime] = None
    ultima_consulta: Optional[datetime] = None
    estado: SecFonteEstado


class AuditoriaOut(BaseModel):
    id: UUID
    user_id: UUID
    acao: str
    detalhe: Optional[str] = None
    ts: datetime


# ---- ativos (M1) ----

class AssetCreate(BaseModel):
    tipo: SecAssetTipo
    identificador: str
    titular: SecTitular = SecTitular.responsavel


class AssetUpdate(BaseModel):
    titular: Optional[SecTitular] = None


class AssetOut(BaseModel):
    id: UUID
    tipo: SecAssetTipo
    identificador_mascarado: str
    titular: SecTitular
    nivel_autorizacao: SecNivelAutorizacao
    verificado_em: Optional[datetime] = None
    ativo: bool
    ultima_verificacao: Optional[datetime] = None
    created_at: datetime


# ---- incidentes (M2) ----
from app.models.secintel import (  # noqa: E402
    SecIncidenteEstado,
    SecItemTipo,
    SecSeveridade,
)


class IncidenteOut(BaseModel):
    id: UUID
    titulo: str
    cenario: str
    severidade: SecSeveridade
    score: int
    confianca: float
    estado: SecIncidenteEstado
    primeiro_visto: datetime
    ultimo_visto: datetime
    ocorrencias: int
    resumo: str


class ItemOut(BaseModel):
    id: UUID
    ref_tipo: SecItemTipo
    ref_id: Optional[UUID] = None
    nota: Optional[str] = None
    ts: datetime


class RecomendacaoOut(BaseModel):
    titulo: str
    bloco: str
    feito: bool


class IncidenteDetalheOut(IncidenteOut):
    recomendacoes: list[RecomendacaoOut]
    itens: list[ItemOut]


class TransicaoIn(BaseModel):
    estado: SecIncidenteEstado


class RecomendacaoPatch(BaseModel):
    feito: bool
