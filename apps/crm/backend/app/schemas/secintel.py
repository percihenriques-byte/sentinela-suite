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
