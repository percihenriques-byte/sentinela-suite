"""Modelos do modulo Sentinela (controle parental) dentro da suite.

Diferente do resto do CRM, estes dados NAO sao workspace-scoped: o registro de
supervisao pertence a maquina/familia, nao a um espaco de trabalho comercial.
Qualquer usuario autenticado desta instalacao local e, por definicao, o
responsavel — o app roda em 127.0.0.1, na casa da pessoa.

O texto da busca e material sensivel (é o que uma crianca digitou), entao vai
cifrado em repouso com o mesmo Fernet que o CRM ja usa para tokens.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field

from app.models.base import TimestampedModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SentinelaEvent(TimestampedModel, table=True):
    """Uma tentativa observada (busca, pagina ou imagem) e o veredito da IA local.

    Quem classifica e o classificador do Sentinela (PowerShell, espelhado em JS
    na extensao). O servidor NAO reimplementa a classificacao — seria uma
    terceira copia da mesma regra. Ele guarda o veredito recebido.
    """

    ocorrido_em: datetime = Field(default_factory=_now, index=True, nullable=False)
    busca_enc: str = Field(default="", nullable=False)  # Fernet
    origem: str = Field(default="desconhecida", index=True)  # google | youtube | pagina | imagem | app
    dispositivo: str = Field(default="este-pc", index=True)
    tema: Optional[str] = Field(default=None, index=True)
    confianca: float = Field(default=0.0)
    bloqueado: bool = Field(default=False, index=True)
    sinais: Optional[str] = Field(default=None)  # termos que dispararam, separados por virgula


class SentinelaConfig(TimestampedModel, table=True):
    """Configuracao do modulo — linha unica (singleton) por instalacao."""

    ativo: bool = Field(default=True)
    sensibilidade: str = Field(default="media")  # baixa | media | alta
    token_ingestao: str = Field(default="", nullable=False)
    pin_hash: Optional[str] = Field(default=None)
    retencao_dias: int = Field(default=90)
