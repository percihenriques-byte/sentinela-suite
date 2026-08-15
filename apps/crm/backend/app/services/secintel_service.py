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
import re
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


def _idade_dias(quando: Optional[datetime]) -> float:
    """Idade em dias de um timestamp. O SQLite devolve datetimes naive (o app
    grava sempre UTC), entao normalizamos antes de subtrair."""
    if quando is None:
        return 0.0
    if quando.tzinfo is None:
        quando = quando.replace(tzinfo=timezone.utc)
    return max(0.0, (_now() - quando).total_seconds() / 86400.0)


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
            "para saber se apareceu em vazamentos. Senhas NUNCA sao enviadas — "
            "esta fonte so verifica e-mail. Exige uma chave de API do HIBP, "
            "configurada aqui e guardada cifrada."
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
            "subdominios inesperados. Tambem resolve DNS TXT (via dns.google) "
            "para comprovar a posse do dominio. Sai da maquina: o nome do dominio."
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

# Validacao de formato por tipo: barra lixo antes de cifrar/consultar. Um
# repo mal-formado nunca vira URL de tarball; um dominio mal-formado nunca
# vira consulta DNS. Lenient de proposito — so recusa o que jamais seria
# valido, sem impor politica de nomes. Tipos livres (username, dispositivo,
# conta_externa) nao tem formato canonico e passam com o strip/nao-vazio.
_RE_REPO = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
_RE_DOMINIO = re.compile(
    r"^(?=.{1,253}$)([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,}$"
)
_RE_EMAIL = re.compile(r"^[^@\s]+@([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,}$")


def _validar_identificador(tipo: SecAssetTipo, identificador: str) -> None:
    """Recusa (422) identificadores que jamais poderiam ser o que o tipo diz
    ser. So os tipos com formato canonico (repo, dominio, subdominio, email,
    api_endpoint) sao checados; os demais sao livres."""
    if tipo == SecAssetTipo.repo:
        if not _RE_REPO.match(identificador):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "repositorio deve ter o formato dono/nome",
            )
    elif tipo in (SecAssetTipo.dominio, SecAssetTipo.subdominio):
        if not _RE_DOMINIO.match(identificador.lower()):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "dominio invalido (ex.: exemplo.com)",
            )
    elif tipo == SecAssetTipo.email:
        if not _RE_EMAIL.match(identificador):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "e-mail invalido",
            )
    elif tipo == SecAssetTipo.api_endpoint:
        if not re.match(r"^https?://", identificador, re.IGNORECASE):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "endpoint deve comecar com http:// ou https://",
            )


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
    _validar_identificador(tipo, identificador)
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


def token_desafio_dominio(workspace_id: UUID, identificador: str) -> str:
    """Token deterministico do desafio DNS TXT de um dominio. Derivado do
    APP_SECRET_KEY — inforjavel sem o segredo, e recalculavel pela UI e pelo
    verificador sem precisar guardar nada."""
    import hashlib
    import hmac

    from app.core.config import get_settings

    segredo = get_settings().app_secret_key.encode()
    msg = f"{workspace_id}:{identificador.strip().lower()}".encode()
    return hmac.new(segredo, msg, hashlib.sha256).hexdigest()[:20]


def desafio_posse(workspace_id: UUID, tipo: SecAssetTipo, identificador: str) -> Optional[str]:
    """Registro que o usuario deve criar para comprovar posse (so dominio)."""
    if tipo in (SecAssetTipo.dominio, SecAssetTipo.subdominio):
        return f"sentinela-verify={token_desafio_dominio(workspace_id, identificador)}"
    return None


def verificar_posse(
    session: Session, workspace_id: UUID, user: User, asset_id: UUID, verificadores=None,
) -> tuple[SecAsset, str]:
    """Reavalia a posse de um ativo. Devolve (asset, motivo).

    Verificacao POR REDE (F2), sempre dentro do consentimento: repo so verifica
    com a fonte github_secrets HABILITADA (e token configurado); dominio so com
    a fonte ct HABILITADA. Fonte desligada NUNCA dispara rede — cai em declarado
    com motivo. O e-mail de login segue verificado localmente, sem rede."""
    from app.services.secintel_scheduler import _verificadores_reais

    asset = get_asset(session, workspace_id, asset_id)
    identificador = crypto.decrypt(asset.identificador_enc)
    verificadores = verificadores or _verificadores_reais()
    asset.ultima_verificacao = _now()

    nivel = SecNivelAutorizacao.declarado
    motivo = ""

    if asset.tipo == SecAssetTipo.email:
        nivel, verif = _avaliar_posse(session, user, asset.tipo, identificador)
        motivo = "e-mail de login (verificado localmente)" if nivel == SecNivelAutorizacao.verificado \
            else "e-mail de terceiro — sem como comprovar posse localmente"

    elif asset.tipo == SecAssetTipo.repo:
        fonte = _fonte(session, "github_secrets")
        if not (fonte and fonte.habilitada):
            motivo = "ligue a fonte 'github_secrets' para verificar a posse do repositorio"
        elif not fonte.credencial_enc:
            motivo = "configure o token do GitHub na fonte para verificar a posse"
        else:
            token = crypto.decrypt(fonte.credencial_enc)
            if verificadores["repo"](identificador, token):
                nivel = SecNivelAutorizacao.verificado
                motivo = "posse comprovada: seu token tem permissao de escrita no repositorio"
            else:
                motivo = "o token nao tem permissao de escrita neste repositorio"

    elif asset.tipo in (SecAssetTipo.dominio, SecAssetTipo.subdominio):
        fonte = _fonte(session, "ct")
        if not (fonte and fonte.habilitada):
            motivo = "ligue a fonte 'ct' para verificar a posse do dominio (consulta DNS)"
        else:
            token = token_desafio_dominio(workspace_id, identificador)
            if verificadores["dominio"](identificador, token):
                nivel = SecNivelAutorizacao.verificado
                motivo = "posse comprovada: registro DNS TXT encontrado"
            else:
                motivo = (f"crie um registro TXT 'sentinela-verify={token}' no dominio "
                          "e clique em verificar novamente")
    else:
        motivo = "este tipo de ativo nao tem verificacao de posse por rede"

    asset.nivel_autorizacao = nivel
    if nivel == SecNivelAutorizacao.verificado and asset.verificado_em is None:
        asset.verificado_em = _now()
    if nivel != SecNivelAutorizacao.verificado:
        asset.verificado_em = None
    session.add(asset)
    session.commit()
    session.refresh(asset)
    registrar_auditoria(session, workspace_id, user.id, "ativo_verificado",
                        {"asset_id": str(asset_id), "nivel": nivel.value})
    return asset, motivo


def _fonte(session, nome):
    garantir_fontes(session)
    return session.exec(select(SecFonte).where(SecFonte.nome == nome)).first()


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
from app.services import secintel_score as score_engine  # noqa: E402

# allowlist de atributos por evento — nunca guardamos payload bruto (ESPEC 12)
_ATRIBUTOS_OK = {"user_agent_familia", "motivo", "endpoint"}

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
    _peso_nivel = {"suspeita": 1, "incidente": 2}
    candidatos: dict[str, regras.Hit] = {}
    for h in hits:
        if h.nivel == "indicador":
            continue
        fp = _fingerprint_incidente(h.cenario, h.usuario)
        atual = candidatos.get(fp)
        if atual is None:
            candidatos[fp] = h
            continue
        # Hits do mesmo incidente (ex.: duas ondas do mesmo ataque no dia):
        # fica o de maior nivel, mas as EVIDENCIAS se UNEM — sem isso, os
        # eventos da segunda onda nunca chegariam a linha do tempo e a
        # reincidencia real passaria despercebida.
        escolhido = h if _peso_nivel[h.nivel] > _peso_nivel[atual.nivel] else atual
        outro = atual if escolhido is h else h
        escolhido.chaves = set(escolhido.chaves) | set(outro.chaves)
        escolhido.evento_ids = list(dict.fromkeys(
            list(escolhido.evento_ids) + list(outro.evento_ids)
        ))
        candidatos[fp] = escolhido

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
    # Scoring completo (ESPEC secao 9). Incidentes de correlacao local afetam a
    # conta do responsavel (impacto 1.0) e NAO tem achado CONFIRMED por tras,
    # entao confirmado=False — por construcao nunca chegam a CRITICAL (a trava
    # os mantem em HIGH no maximo).
    p = score_engine.P_FORTE if h.nivel == "incidente" else score_engine.P_MEDIA
    confianca = 0.8 if h.nivel == "incidente" else 0.5
    score, sev = score_engine.calcular(
        p=p, impacto=1.0, confianca=confianca, idade_dias=0.0,
        chaves_extra=len(h.chaves) - 1, confirmado=False,
    )

    if inc is None:
        inc = SecIncidente(
            workspace_id=workspace_id, titulo=h.titulo, cenario=h.cenario,
            severidade=sev, score=score, confianca=confianca,
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
        # Reincidencia REAL exige evento novo. O laco de correlacao roda a cada
        # 5 min sobre a mesma janela de 24h: sem esta guarda, o MESMO conjunto
        # de eventos incrementava `ocorrencias` e poluia a linha do tempo a
        # cada ciclo (~288 notas/dia para um ataque unico).
        ja_contados = {
            i.ref_id for i in itens_do_incidente(session, inc.id)
            if i.ref_tipo == SecItemTipo.evento and i.ref_id is not None
        }
        novos = [eid for eid in h.evento_ids if eid not in ja_contados]
        if not novos:
            return inc  # mesma evidencia de sempre: nada a atualizar
        inc.ultimo_visto = _now()
        inc.ocorrencias += 1
        # escala severidade/score se o novo hit for mais grave
        if score > inc.score:
            inc.severidade = sev
            inc.titulo = h.titulo
            inc.resumo = h.resumo
        inc.score = max(inc.score, score)
        session.add(inc)
        session.commit()
        session.refresh(inc)
        for eid in novos:
            _add_item(session, inc.id, SecItemTipo.evento, ref_id=eid)
        _add_item(session, inc.id, SecItemTipo.nota,
                  nota=f"Reincidencia ({inc.ocorrencias}x): {len(novos)} evento(s) novo(s)")
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


def marcar_recomendacao(session, workspace_id, user_id, incidente_id, indice: int, feito: bool):
    inc = get_incidente(session, workspace_id, incidente_id)
    recs = json.loads(inc.recomendacoes or "[]")
    if indice < 0 or indice >= len(recs):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "recomendacao inexistente")
    recs[indice]["feito"] = feito
    inc.recomendacoes = json.dumps(recs, ensure_ascii=False)
    session.add(inc)
    session.commit()
    session.refresh(inc)
    registrar_auditoria(
        session, workspace_id, user_id, "recomendacao_marcada",
        {"incidente_id": str(incidente_id), "indice": indice, "feito": feito},
    )
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


# ---- achados: leitura + loop de falso-positivo (M3) -----------------------

from app.models.secintel import (  # noqa: E402
    SecAchado,
    SecAchadoStatus,
    SecClassificacao,
)


def listar_achados(session, workspace_id, *, status_f=None, severidade=None, fonte=None):
    q = select(SecAchado).where(
        SecAchado.workspace_id == workspace_id, SecAchado.deleted_at.is_(None)
    )
    if status_f is not None:
        q = q.where(SecAchado.status == status_f)
    if severidade is not None:
        q = q.where(SecAchado.severidade == severidade)
    if fonte is not None:
        q = q.where(SecAchado.fonte == fonte)
    return list(session.exec(q.order_by(SecAchado.descoberto_em.desc())))


def get_achado(session, workspace_id, achado_id) -> SecAchado:
    a = session.get(SecAchado, achado_id)
    if not a or a.workspace_id != workspace_id or a.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "achado nao encontrado")
    return a


def marcar_falso_positivo(session, workspace_id, user_id, achado_id, motivo: str):
    """Loop de falso-positivo (ESPEC Fase 8): FP exige MOTIVO, e registrado (nao
    descartado em silencio) e nunca vira incidente."""
    motivo = (motivo or "").strip()
    if not motivo:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "motivo obrigatorio para falso-positivo")
    a = get_achado(session, workspace_id, achado_id)
    a.status = SecAchadoStatus.falso_positivo
    a.classificacao = SecClassificacao.false_positive
    a.confianca = 0.0
    a.motivo_fp = motivo
    session.add(a)
    session.commit()
    session.refresh(a)
    registrar_auditoria(session, workspace_id, user_id, "achado_falso_positivo",
                        {"achado_id": str(achado_id)})
    return a


def marcar_resolvido(session, workspace_id, user_id, achado_id):
    a = get_achado(session, workspace_id, achado_id)
    a.status = SecAchadoStatus.resolvido
    session.add(a)
    session.commit()
    session.refresh(a)
    registrar_auditoria(session, workspace_id, user_id, "achado_resolvido",
                        {"achado_id": str(achado_id)})
    return a


# ---- visao geral (M3) -----------------------------------------------------

def visao_geral(session, workspace_id) -> dict:
    """Agregado para a tela inicial: score do workspace, contadores por
    severidade, fontes ligadas e ultimos incidentes/achados."""
    incidentes = listar_incidentes(session, workspace_id)
    abertos = [i for i in incidentes
               if i.estado not in (SecIncidenteEstado.fechado, SecIncidenteEstado.falso_positivo)]
    achados = [a for a in listar_achados(session, workspace_id)
               if a.status not in (SecAchadoStatus.falso_positivo, SecAchadoStatus.resolvido)]

    por_sev_inc: dict[str, int] = {}
    for i in abertos:
        por_sev_inc[i.severidade.value] = por_sev_inc.get(i.severidade.value, 0) + 1
    por_sev_ach: dict[str, int] = {}
    for a in achados:
        por_sev_ach[a.severidade.value] = por_sev_ach.get(a.severidade.value, 0) + 1

    # score do workspace = maior score entre incidentes abertos e achados ativos.
    # Achados usam a IDADE REAL (decaimento por recencia, ESPEC secao 9): uma
    # exposicao de meses atras nao pesa como uma de hoje.
    scores = [i.score for i in abertos] + [
        score_engine.calcular(
            p=score_engine.P_FORTE,
            impacto=1.0,
            confianca=a.confianca,
            idade_dias=_idade_dias(a.descoberto_em),
            confirmado=(a.classificacao == SecClassificacao.confirmed),
        )[0]
        for a in achados
    ]
    score_ws = max(scores) if scores else 0

    fontes = garantir_fontes(session)
    return {
        "score": score_ws,
        "severidade": score_engine.banda(score_ws).value,
        "incidentes_abertos": len(abertos),
        "achados_ativos": len(achados),
        "por_severidade_incidentes": por_sev_inc,
        "por_severidade_achados": por_sev_ach,
        "fontes_ligadas": [f.nome for f in fontes if f.habilitada],
        "fontes_desligadas": [f.nome for f in fontes if not f.habilitada],
        "ultimos_incidentes": [i.id for i in incidentes[:5]],
    }


# ---- consentimento de fontes (M4) -----------------------------------------

def alternar_fonte(session, workspace_id, user_id, nome: str, habilitada: bool):
    """Liga/desliga uma fonte. Ligar registra o consentimento (quem/quando);
    desligar o limpa. Auditado nos dois sentidos. `eventos_locais` (100% local)
    nao pode ser desligada — e a base do plano local."""
    garantir_fontes(session)
    fonte = session.exec(select(SecFonte).where(SecFonte.nome == nome)).first()
    if not fonte:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "fonte desconhecida")
    if nome == "eventos_locais" and not habilitada:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "a fonte local nao pode ser desligada")
    # gate de credencial (E1): fonte que exige chave nao liga sem chave — assim
    # o usuario recebe uma mensagem clara em vez de ligar e a fonte falhar.
    if habilitada:
        from app.services import secintel_fontes
        adapter = secintel_fontes.ADAPTERS.get(nome)
        if adapter and getattr(adapter, "EXIGE_CREDENCIAL", False) and not fonte.credencial_enc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"a fonte '{nome}' exige uma chave de API; configure-a antes de ligar",
            )
    fonte.habilitada = habilitada
    if habilitada:
        fonte.consentida_em = _now()
        fonte.consentida_por = user_id
    else:
        fonte.consentida_em = None
        fonte.consentida_por = None
    session.add(fonte)
    session.commit()
    session.refresh(fonte)
    registrar_auditoria(
        session, workspace_id, user_id,
        "fonte_habilitada" if habilitada else "fonte_desabilitada",
        {"fonte": nome},
    )
    return fonte


def rodar_exposicao(session, workspace_id, transportes=None):
    """Roda as fontes de exposicao habilitadas. Delegado ao runner que garante
    a trava de consentimento (fonte desligada nunca e chamada)."""
    from app.services import secintel_fontes
    return secintel_fontes.executar_exposicao(session, workspace_id, transportes=transportes)


def definir_credencial_fonte(session, workspace_id, user_id, nome: str, credencial: str):
    """Grava a credencial (chave de API / token) de uma fonte, CIFRADA. Passar
    string vazia remove a credencial. Auditado; o valor nunca e logado."""
    garantir_fontes(session)
    fonte = session.exec(select(SecFonte).where(SecFonte.nome == nome)).first()
    if not fonte:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "fonte desconhecida")
    credencial = (credencial or "").strip()
    fonte.credencial_enc = crypto.encrypt(credencial) if credencial else None
    session.add(fonte)
    session.commit()
    session.refresh(fonte)
    registrar_auditoria(
        session, workspace_id, user_id,
        "fonte_credencial_definida" if credencial else "fonte_credencial_removida",
        {"fonte": nome},
    )
    return fonte


# ---- higiene / retencao (M5) ----------------------------------------------

# Retencoes (ESPEC secao 12). Em dias. Poderiam vir de Settings; ficam aqui com
# piso documentado porque sao promessa de privacidade, nao ajuste operacional.
RETENCAO_EVENTO_DIAS = 30
RETENCAO_ACHADO_DIAS = 365
RETENCAO_INCIDENTE_FECHADO_DIAS = 180
RETENCAO_AUDITORIA_DIAS = 365
FECHAR_RECUPERADO_APOS_DIAS = 30


def aplicar_higiene(session) -> dict:
    """Aplica retencoes e fecha incidentes recuperados ha muito tempo. Global
    (todas as instalacoes locais tem um workspace); best-effort no scheduler."""
    from app.models.secintel import SecAchado

    agora = _now()
    contadores = {"eventos": 0, "achados": 0, "incidentes": 0, "auditoria": 0, "fechados": 0}

    # fecha incidentes 'recuperado' ha mais de N dias
    corte_rec = agora - timedelta(days=FECHAR_RECUPERADO_APOS_DIAS)
    for inc in session.exec(select(SecIncidente).where(
        SecIncidente.estado == SecIncidenteEstado.recuperado,
        SecIncidente.deleted_at.is_(None),
        SecIncidente.ultimo_visto < corte_rec,
    )):
        inc.estado = SecIncidenteEstado.fechado
        session.add(inc)
        contadores["fechados"] += 1

    # purga por retencao (soft-delete via deleted_at)
    def _purgar(modelo, campo, dias):
        corte = agora - timedelta(days=dias)
        n = 0
        for row in session.exec(select(modelo).where(
            modelo.deleted_at.is_(None), campo < corte,
        )):
            row.deleted_at = agora
            session.add(row)
            n += 1
        return n

    contadores["eventos"] = _purgar(SecEvento, SecEvento.ts, RETENCAO_EVENTO_DIAS)
    contadores["achados"] = _purgar(SecAchado, SecAchado.descoberto_em, RETENCAO_ACHADO_DIAS)
    contadores["auditoria"] = _purgar(SecAuditoria, SecAuditoria.ts, RETENCAO_AUDITORIA_DIAS)
    # incidentes fechados/FP ha mais de N dias
    corte_inc = agora - timedelta(days=RETENCAO_INCIDENTE_FECHADO_DIAS)
    for inc in session.exec(select(SecIncidente).where(
        SecIncidente.estado.in_([SecIncidenteEstado.fechado, SecIncidenteEstado.falso_positivo]),
        SecIncidente.deleted_at.is_(None),
        SecIncidente.ultimo_visto < corte_inc,
    )):
        inc.deleted_at = agora
        session.add(inc)
        contadores["incidentes"] += 1

    session.commit()
    return contadores


def workspaces_ativos(session) -> list[UUID]:
    from app.models import Workspace

    return [w.id for w in session.exec(
        select(Workspace).where(Workspace.deleted_at.is_(None), Workspace.is_active.is_(True))
    )]
