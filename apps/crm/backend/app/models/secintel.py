"""Modelos do modulo Seguranca (Security Intelligence Engine).

Ver ESPEC-SEGURANCA.md (raiz do monorepo), secao 3. Principios que estes
modelos carregam:

* Nenhum segredo em claro: o identificador do ativo vai cifrado (Fernet, o
  mesmo de core/crypto.py) + um hash sha256 para busca/dedupe + uma versao
  mascarada para listagem. Valores de secrets achados NUNCA sao persistidos —
  so o mascarado e um fingerprint.
* Dedupe por fingerprint: achado/incidente repetido ATUALIZA a linha existente
  (ultimo_visto, ocorrencias), nunca duplica.
* Escopo de workspace em tudo que e dado do usuario; `secfonte` e global da
  instalacao (o consentimento de egresso e da maquina, nao de um workspace).
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlmodel import Field

from app.models.base import TimestampedModel, WorkspaceScopedModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---- enums ----------------------------------------------------------------

class SecAssetTipo(str, Enum):
    email = "email"
    dominio = "dominio"
    subdominio = "subdominio"
    username = "username"
    repo = "repo"
    dispositivo = "dispositivo"
    api_endpoint = "api_endpoint"
    conta_externa = "conta_externa"


class SecTitular(str, Enum):
    responsavel = "responsavel"
    crianca = "crianca"
    organizacao = "organizacao"


class SecNivelAutorizacao(str, Enum):
    verificado = "verificado"
    declarado = "declarado"


class SecEventoOrigem(str, Enum):
    painel_auth = "painel_auth"
    sentinela_pin = "sentinela_pin"
    ingestao = "ingestao"
    rate_limit = "rate_limit"
    dispositivo = "dispositivo"
    extensao = "extensao"


class SecTipoExposicao(str, Enum):
    email_em_vazamento = "email_em_vazamento"
    senha_comprometida = "senha_comprometida"
    api_key = "api_key"
    token = "token"
    private_key = "private_key"
    connection_string = "connection_string"
    secret_generico = "secret_generico"
    documento_exposto = "documento_exposto"
    repositorio_com_secret = "repositorio_com_secret"
    dado_pessoal_exposto = "dado_pessoal_exposto"


class SecClassificacao(str, Enum):
    confirmed = "CONFIRMED"
    likely = "LIKELY"
    possible = "POSSIBLE"
    false_positive = "FALSE_POSITIVE"


class SecSeveridade(str, Enum):
    info = "INFO"
    low = "LOW"
    medium = "MEDIUM"
    high = "HIGH"
    critical = "CRITICAL"


class SecAchadoStatus(str, Enum):
    novo = "novo"
    validado = "validado"
    falso_positivo = "falso_positivo"
    resolvido = "resolvido"
    mesclado = "mesclado"


class SecIncidenteEstado(str, Enum):
    detectado = "detectado"
    triagem = "triagem"
    contido = "contido"
    remediado = "remediado"
    recuperado = "recuperado"
    fechado = "fechado"
    falso_positivo = "falso_positivo"


class SecFonteEstado(str, Enum):
    ok = "ok"
    erro = "erro"
    rate_limited = "rate_limited"


class SecItemTipo(str, Enum):
    evento = "evento"
    achado = "achado"
    nota = "nota"
    transicao = "transicao"


# ---- tabelas --------------------------------------------------------------

class SecAsset(WorkspaceScopedModel, table=True):
    """Um ativo que o modulo esta AUTORIZADO a proteger (ESPEC secao 2)."""

    tipo: SecAssetTipo = Field(index=True, nullable=False)
    identificador_enc: str = Field(nullable=False)          # Fernet
    identificador_hash: str = Field(index=True, nullable=False)  # sha256 hex
    identificador_mascarado: str = Field(nullable=False)
    titular: SecTitular = Field(default=SecTitular.responsavel, nullable=False)
    nivel_autorizacao: SecNivelAutorizacao = Field(
        default=SecNivelAutorizacao.declarado, nullable=False
    )
    verificado_em: Optional[datetime] = Field(default=None)
    fonte_cadastro: str = Field(default="manual")
    ativo: bool = Field(default=True, index=True)
    ultima_verificacao: Optional[datetime] = Field(default=None)


class SecFonte(TimestampedModel, table=True):
    """Fonte de consulta. Global da instalacao; nasce DESLIGADA (opt-in).

    `descricao_egresso` e o texto mostrado na UX ANTES de ligar: exatamente o
    que sai da maquina quando esta fonte consulta. Ligar registra quem/quando.
    """

    nome: str = Field(index=True, unique=True, nullable=False)
    habilitada: bool = Field(default=False, nullable=False)
    requer_nivel: SecNivelAutorizacao = Field(
        default=SecNivelAutorizacao.verificado, nullable=False
    )
    descricao_egresso: str = Field(nullable=False)
    # credencial da fonte (ex.: chave de API do HIBP, token GitHub), cifrada
    # com Fernet. NUNCA sai em resposta de API — só `tem_credencial: bool`.
    credencial_enc: Optional[str] = Field(default=None)
    consentida_em: Optional[datetime] = Field(default=None)
    consentida_por: Optional[UUID] = Field(default=None, foreign_key="user.id")
    ultima_consulta: Optional[datetime] = Field(default=None)
    estado: SecFonteEstado = Field(default=SecFonteEstado.ok)
    erro_msg: Optional[str] = Field(default=None)


class SecEvento(WorkspaceScopedModel, table=True):
    """Evento normalizado para correlacao. Retencao curta (30 dias).

    `atributos` e JSON minimizado por allowlist — nunca payload bruto.
    """

    origem: SecEventoOrigem = Field(index=True, nullable=False)
    tipo: str = Field(index=True, nullable=False)
    ts: datetime = Field(default_factory=_now, index=True, nullable=False)
    ip: Optional[str] = Field(default=None, index=True)
    usuario: Optional[str] = Field(default=None, index=True)
    dispositivo_id: Optional[str] = Field(default=None)
    sessao: Optional[str] = Field(default=None)
    endpoint: Optional[str] = Field(default=None)
    atributos: Optional[str] = Field(default=None)  # JSON string minimizado


class SecAchado(WorkspaceScopedModel, table=True):
    """Uma exposicao detectada. O valor sensivel NAO existe aqui: apenas o
    `indicador_mascarado` e o fingerprint para dedupe."""

    asset_id: Optional[UUID] = Field(default=None, foreign_key="secasset.id", index=True)
    fonte: str = Field(index=True, nullable=False)
    tipo_exposicao: SecTipoExposicao = Field(index=True, nullable=False)
    classificacao: SecClassificacao = Field(default=SecClassificacao.possible, nullable=False)
    confianca: float = Field(default=0.4, nullable=False)
    severidade: SecSeveridade = Field(default=SecSeveridade.low, index=True, nullable=False)
    indicador_mascarado: str = Field(default="", nullable=False)
    evidencia_resumo: str = Field(default="", nullable=False)  # SEM segredo
    fingerprint: str = Field(index=True, nullable=False)
    descoberto_em: datetime = Field(default_factory=_now, nullable=False)
    exposto_em_estimado: Optional[datetime] = Field(default=None)
    status: SecAchadoStatus = Field(default=SecAchadoStatus.novo, index=True, nullable=False)
    motivo_fp: Optional[str] = Field(default=None)
    incidente_id: Optional[UUID] = Field(default=None, foreign_key="secincidente.id", index=True)


class SecIncidente(WorkspaceScopedModel, table=True):
    """Incidente correlacionado. Reincidencia atualiza (nunca duplica)."""

    titulo: str = Field(nullable=False)
    cenario: str = Field(index=True, nullable=False)  # chave do threat model (ESPEC secao 13)
    severidade: SecSeveridade = Field(default=SecSeveridade.medium, index=True, nullable=False)
    score: int = Field(default=0, nullable=False)
    confianca: float = Field(default=0.4, nullable=False)
    estado: SecIncidenteEstado = Field(
        default=SecIncidenteEstado.detectado, index=True, nullable=False
    )
    fingerprint: str = Field(index=True, nullable=False)
    primeiro_visto: datetime = Field(default_factory=_now, nullable=False)
    ultimo_visto: datetime = Field(default_factory=_now, nullable=False)
    ocorrencias: int = Field(default=1, nullable=False)
    resumo: str = Field(default="", nullable=False)
    recomendacoes: Optional[str] = Field(default=None)  # JSON: [{titulo, bloco, feito}]


class SecIncidenteItem(TimestampedModel, table=True):
    """Linha do tempo do incidente: eventos, achados, notas e transicoes."""

    incidente_id: UUID = Field(foreign_key="secincidente.id", index=True, nullable=False)
    ref_tipo: SecItemTipo = Field(nullable=False)
    ref_id: Optional[UUID] = Field(default=None)
    nota: Optional[str] = Field(default=None)
    ts: datetime = Field(default_factory=_now, nullable=False)


class SecAuditoria(WorkspaceScopedModel, table=True):
    """Trilha de auditoria do proprio modulo: quem viu/mudou o que, quando."""

    user_id: UUID = Field(foreign_key="user.id", index=True, nullable=False)
    acao: str = Field(index=True, nullable=False)
    detalhe: Optional[str] = Field(default=None)  # JSON string
    ts: datetime = Field(default_factory=_now, index=True, nullable=False)
