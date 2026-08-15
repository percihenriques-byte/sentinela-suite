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
from datetime import datetime, timedelta, timezone
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


# ---- eventos + correlacao + incidentes (M2) -------------------------------

from app.models.secintel import (  # noqa: E402
    SecEvento,
    SecEventoOrigem,
    SecIncidente,
    SecIncidenteEstado,
    SecIncidenteItem,
    SecItemTipo,
    SecSeveridade,
)
from app.services import secintel_regras as regras  # noqa: E402

# allowlist de atributos por evento — nunca guardamos payload bruto (ESPEC 12)
_ATRIBUTOS_OK = {"user_agent_familia", "motivo", "endpoint"}

_SEV_SCORE = {  # score-base do M2; o M3 substitui pelo scoring completo
    "INFO": 5, "LOW": 20, "MEDIUM": 40, "HIGH": 65, "CRITICAL": 85,
}

JANELA_CORRELACAO_S = 24 * 60 * 60


def registrar_evento(
    session: Session,
    workspace_id: UUID,
    origem: SecEventoOrigem,
    tipo: str,
    *,
    ip: Optional[str] = None,
    usuario: Optional[str] = None,
    dispositivo_id: Optional[str] = None,
    sessao: Optional[str] = None,
    endpoint: Optional[str] = None,
    atributos: Optional[dict] = None,
) -> SecEvento:
    """Normaliza e grava um evento para correlacao. `atributos` e minimizado
    por allowlist. `usuario` deve ser um identificador estavel (ex.: e-mail),
    nao um segredo."""
    minimizado = None
    if atributos:
        limpo = {k: v for k, v in atributos.items() if k in _ATRIBUTOS_OK}
        if limpo:
            minimizado = json.dumps(limpo, ensure_ascii=False)
    ev = SecEvento(
        workspace_id=workspace_id, origem=origem, tipo=tipo, ts=_now(),
        ip=ip, usuario=usuario, dispositivo_id=dispositivo_id,
        sessao=sessao, endpoint=endpoint, atributos=minimizado,
    )
    session.add(ev)
    session.commit()
    session.refresh(ev)
    return ev


def listar_eventos(session: Session, workspace_id: UUID, limit: int = 100) -> list[SecEvento]:
    return list(session.exec(
        select(SecEvento)
        .where(SecEvento.workspace_id == workspace_id, SecEvento.deleted_at.is_(None))
        .order_by(SecEvento.ts.desc()).limit(min(limit, 500))
    ))


def _fingerprint_incidente(cenario: str, usuario: Optional[str]) -> str:
    dia = _now().strftime("%Y-%m-%d")
    return mascara.fingerprint(cenario, usuario or "-", dia)


def correlacionar(session: Session, workspace_id: UUID) -> list[SecIncidente]:
    """Roda as regras sobre a janela quente de eventos e cria/atualiza
    incidentes. Dedupe por fingerprint (cenario|usuario|dia): reincidencia
    ATUALIZA o incidente existente, nunca duplica (ESPEC Fase 10)."""
    corte = _now() - timedelta(seconds=JANELA_CORRELACAO_S)
    eventos = list(session.exec(
        select(SecEvento).where(
            SecEvento.workspace_id == workspace_id,
            SecEvento.deleted_at.is_(None),
            SecEvento.ts >= corte,
        )
    ))
    hits = regras.avaliar(eventos)
    # so viram incidente: suspeitas e incidentes (indicadores ficam como sinal
    # e alimentam as regras compostas). Entre hits do mesmo cenario+usuario, o
    # de maior severidade vence.
    candidatos: dict[str, regras.Hit] = {}
    for h in hits:
        if h.nivel == "indicador":
            continue
        fp = _fingerprint_incidente(h.cenario, h.usuario)
        atual = candidatos.get(fp)
        if atual is None or _SEV_SCORE[h.severidade] > _SEV_SCORE[atual.severidade]:
            candidatos[fp] = h

    tocados = []
    for fp, h in candidatos.items():
        inc = _upsert_incidente(session, workspace_id, fp, h)
        tocados.append(inc)
    return tocados


def _upsert_incidente(session, workspace_id, fp, h: "regras.Hit") -> SecIncidente:
    inc = session.exec(
        select(SecIncidente).where(
            SecIncidente.workspace_id == workspace_id,
            SecIncidente.fingerprint == fp,
            SecIncidente.deleted_at.is_(None),
        )
    ).first()
    score = _SEV_SCORE[h.severidade] + min(30, 10 * max(0, len(h.chaves) - 1))
    score = min(100, score)
    confianca = {"suspeita": 0.5, "incidente": 0.8}.get(h.nivel, 0.5)

    if inc is None:
        inc = SecIncidente(
            workspace_id=workspace_id, titulo=h.titulo, cenario=h.cenario,
            severidade=SecSeveridade(h.severidade), score=score, confianca=confianca,
            estado=SecIncidenteEstado.detectado, fingerprint=fp,
            primeiro_visto=_now(), ultimo_visto=_now(), ocorrencias=1,
            resumo=h.resumo, recomendacoes=json.dumps(_recomendacoes(h.cenario), ensure_ascii=False),
        )
        session.add(inc)
        session.commit()
        session.refresh(inc)
        _add_item(session, inc.id, SecItemTipo.nota, nota=f"Incidente aberto: {h.titulo}")
        for eid in h.evento_ids:
            _add_item(session, inc.id, SecItemTipo.evento, ref_id=eid)
    else:
        inc.ultimo_visto = _now()
        inc.ocorrencias += 1
        # escala severidade/score se o novo hit for mais grave
        if _SEV_SCORE[h.severidade] > _SEV_SCORE[inc.severidade.value]:
            inc.severidade = SecSeveridade(h.severidade)
            inc.titulo = h.titulo
            inc.resumo = h.resumo
        inc.score = max(inc.score, score)
        session.add(inc)
        session.commit()
        session.refresh(inc)
        _add_item(session, inc.id, SecItemTipo.nota,
                  nota=f"Reincidencia ({inc.ocorrencias}x)")
    return inc


def _add_item(session, incidente_id, ref_tipo, ref_id=None, nota=None):
    session.add(SecIncidenteItem(
        incidente_id=incidente_id, ref_tipo=ref_tipo, ref_id=ref_id, nota=nota, ts=_now(),
    ))
    session.commit()


# recomendacoes por cenario (ESPEC secao 13): DETECCAO ja esta no incidente;
# aqui vao CONTENCAO/REMEDIACAO/RECUPERACAO como itens acionaveis.
_RECOMENDACOES: dict[str, list[tuple[str, str]]] = {
    "account_takeover": [
        ("Encerrar todas as sessoes ativas", "contencao"),
        ("Trocar a senha do painel", "remediacao"),
        ("Ativar verificacao em duas etapas (MFA)", "remediacao"),
        ("Revisar acessos e dispositivos recentes", "recuperacao"),
    ],
    "session_hijacking": [
        ("Encerrar as sessoes ativas", "contencao"),
        ("Trocar a senha do painel", "remediacao"),
        ("Revisar os dispositivos conectados", "recuperacao"),
    ],
    "brute_force": [
        ("Confirmar que o limite de tentativas esta ativo", "contencao"),
        ("Revisar a forca da senha e do PIN", "remediacao"),
        ("Acompanhar novas tentativas", "recuperacao"),
    ],
    "api_key_exposure": [
        ("Revogar o token suspeito", "contencao"),
        ("Rotacionar a chave e remover do repositorio", "remediacao"),
        ("Auditar onde a chave foi usada", "recuperacao"),
    ],
}


def _recomendacoes(cenario: str) -> list[dict]:
    base = _RECOMENDACOES.get(cenario, [("Revisar o alerta", "contencao")])
    return [{"titulo": t, "bloco": b, "feito": False} for t, b in base]


# ---- incidentes: leitura + transicao --------------------------------------

_TRANSICOES = {
    SecIncidenteEstado.detectado: {SecIncidenteEstado.triagem, SecIncidenteEstado.falso_positivo},
    SecIncidenteEstado.triagem: {SecIncidenteEstado.contido, SecIncidenteEstado.falso_positivo},
    SecIncidenteEstado.contido: {SecIncidenteEstado.remediado},
    SecIncidenteEstado.remediado: {SecIncidenteEstado.recuperado},
    SecIncidenteEstado.recuperado: {SecIncidenteEstado.fechado},
    SecIncidenteEstado.fechado: set(),
    SecIncidenteEstado.falso_positivo: set(),
}


def listar_incidentes(session, workspace_id, estado=None):
    q = select(SecIncidente).where(
        SecIncidente.workspace_id == workspace_id, SecIncidente.deleted_at.is_(None)
    )
    if estado is not None:
        q = q.where(SecIncidente.estado == estado)
    return list(session.exec(q.order_by(SecIncidente.ultimo_visto.desc())))


def get_incidente(session, workspace_id, incidente_id) -> SecIncidente:
    inc = session.get(SecIncidente, incidente_id)
    if not inc or inc.workspace_id != workspace_id or inc.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "incidente nao encontrado")
    return inc


def itens_do_incidente(session, incidente_id):
    return list(session.exec(
        select(SecIncidenteItem)
        .where(SecIncidenteItem.incidente_id == incidente_id)
        .order_by(SecIncidenteItem.ts.asc())
    ))


def transicionar(session, workspace_id, user_id, incidente_id, novo: SecIncidenteEstado):
    inc = get_incidente(session, workspace_id, incidente_id)
    if novo not in _TRANSICOES.get(inc.estado, set()):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"transicao invalida: {inc.estado.value} -> {novo.value}",
        )
    anterior = inc.estado
    inc.estado = novo
    session.add(inc)
    session.commit()
    session.refresh(inc)
    _add_item(session, inc.id, SecItemTipo.transicao,
              nota=f"{anterior.value} -> {novo.value}")
    registrar_auditoria(session, workspace_id, user_id, "incidente_transicao",
                        {"incidente_id": str(incidente_id), "de": anterior.value, "para": novo.value})
    return inc


def marcar_recomendacao(session, workspace_id, incidente_id, indice: int, feito: bool):
    inc = get_incidente(session, workspace_id, incidente_id)
    recs = json.loads(inc.recomendacoes or "[]")
    if indice < 0 or indice >= len(recs):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "recomendacao inexistente")
    recs[indice]["feito"] = feito
    inc.recomendacoes = json.dumps(recs, ensure_ascii=False)
    session.add(inc)
    session.commit()
    session.refresh(inc)
    return inc


# ---- captura de eventos do proprio app (best-effort) ----------------------

import logging  # noqa: E402

from app.models import WorkspaceMember  # noqa: E402

_log = logging.getLogger("jarvis.secintel")


def _workspace_do_email(session: Session, email: str) -> Optional[UUID]:
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        return None
    m = session.exec(
        select(WorkspaceMember)
        .where(WorkspaceMember.user_id == user.id, WorkspaceMember.deleted_at.is_(None))
        .order_by(WorkspaceMember.created_at.asc())
        .limit(1)
    ).first()
    return m.workspace_id if m else None


def capturar_login(session: Session, email: str, sucesso: bool, ip: Optional[str]) -> None:
    """Registra login_ok/login_falha para o motor de deteccao. Best-effort:
    qualquer excecao e engolida — observar a seguranca nunca pode derrubar o
    login. Login de usuario desconhecido nao tem workspace para atribuir e e
    ignorado (nao ha o que proteger)."""
    try:
        ws_id = _workspace_do_email(session, email)
        if ws_id is None:
            return
        registrar_evento(
            session, ws_id, SecEventoOrigem.painel_auth,
            "login_ok" if sucesso else "login_falha",
            ip=ip, usuario=(email or "").strip().lower(),
        )
    except Exception:  # pragma: no cover - defensivo
        _log.warning("secintel: falha ao capturar evento de login", exc_info=True)
