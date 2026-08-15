"""Payloads do modulo Seguranca — M0: fontes e auditoria."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.models.secintel import SecFonteEstado, SecNivelAutorizacao


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
