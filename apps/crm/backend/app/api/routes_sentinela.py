"""API do modulo Sentinela — painel do responsavel e ingestao de eventos.

Duas superficies, com credenciais diferentes de proposito:

  * ingestao (`POST /sentinela/eventos`) — usada pela extensao do navegador e
    pelo app PowerShell. Autentica com o token de ingestao (cabecalho
    `X-Sentinela-Token`) e so aceita conexao vinda do loopback. A extensao nao
    tem como carregar um JWT de usuario, e uma rota aberta deixaria qualquer
    processo local forjar (ou poluir) o registro de supervisao.

  * painel (todo o resto) — exige login normal do CRM. Quem esta logado nesta
    instalacao local e o responsavel.

INVARIANTE (nao remover sem substituir por outra guarda): estas rotas nao sao
workspace-scoped de proposito — o registro parental pertence a maquina, nao a um
espaco de trabalho comercial. A consequencia e que QUALQUER usuario autenticado
desta instalacao le o painel. Isso e aceitavel enquanto a instalacao for de uma
familia, com um responsavel. No dia em que o CRM servir usuarios nao
relacionados na mesma instalacao, `CurrentUser` aqui vira brecha: e preciso um
papel `responsavel` no User e um Depends proprio que o exija.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, SessionDep
from app.core.security import hash_password, verify_password
from app.services import sentinela_service as svc

router = APIRouter(prefix="/sentinela", tags=["sentinela"])

LOOPBACK = {"127.0.0.1", "::1", "localhost", "testclient"}


# ----------------------------------------------------------------- schemas


class EventoIn(BaseModel):
    busca: str = Field(min_length=1, max_length=svc.MAX_BUSCA)
    origem: str = "desconhecida"
    dispositivo: str = "este-pc"
    tema: Optional[str] = None
    confianca: float = 0.0
    bloqueado: bool = False
    sinais: list[str] = Field(default_factory=list)
    ocorrido_em: Optional[datetime] = None


class LoteIn(BaseModel):
    eventos: list[EventoIn] = Field(min_length=1, max_length=svc.MAX_LOTE)


class EventoOut(BaseModel):
    id: UUID
    ocorrido_em: datetime
    busca: str
    origem: str
    dispositivo: str
    tema: Optional[str]
    confianca: float
    bloqueado: bool
    sinais: Optional[str]


class ConfigOut(BaseModel):
    ativo: bool
    sensibilidade: str
    retencao_dias: int
    token_ingestao: str
    pin_definido: bool


class ConfigPatch(BaseModel):
    ativo: Optional[bool] = None
    sensibilidade: Optional[str] = None
    retencao_dias: Optional[int] = Field(default=None, ge=0, le=3650)


class PinIn(BaseModel):
    pin: str = Field(min_length=4, max_length=12)
    pin_atual: Optional[str] = None


class PinCheck(BaseModel):
    pin: str


def _para_out(ev) -> EventoOut:
    return EventoOut(
        id=ev.id,
        ocorrido_em=ev.ocorrido_em,
        busca=svc.texto_do_evento(ev),
        origem=ev.origem,
        dispositivo=ev.dispositivo,
        tema=ev.tema,
        confianca=ev.confianca,
        bloqueado=ev.bloqueado,
        sinais=ev.sinais,
    )


def _exige_loopback(request: Request) -> None:
    host = (request.client.host if request.client else "") or ""
    if host not in LOOPBACK:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ingestao aceita apenas do proprio dispositivo")


def _exige_token(session, token: Optional[str]) -> None:
    if not svc.token_confere(session, token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token de ingestao invalido")


# ----------------------------------------------------------------- ingestao


@router.post("/eventos", status_code=status.HTTP_201_CREATED)
def ingerir(
    payload: LoteIn,
    request: Request,
    session: SessionDep,
    x_sentinela_token: Annotated[Optional[str], Header(alias="X-Sentinela-Token")] = None,
) -> dict:
    """Recebe um lote de observacoes da extensao/app. Idempotencia nao se aplica:
    cada tentativa e um fato novo na linha do tempo."""
    _exige_loopback(request)
    _exige_token(session, x_sentinela_token)

    for e in payload.eventos:
        svc.registrar_evento(
            session,
            busca=e.busca,
            origem=e.origem,
            dispositivo=e.dispositivo,
            tema=e.tema,
            confianca=e.confianca,
            bloqueado=e.bloqueado,
            sinais=e.sinais or None,
            ocorrido_em=e.ocorrido_em,
            commit=False,
        )
    session.commit()
    removidos = svc.aplicar_retencao(session)
    return {"registrados": len(payload.eventos), "expirados": removidos}


# ----------------------------------------------------------------- painel


@router.get("/eventos")
def listar(
    session: SessionDep,
    user: CurrentUser,
    limite: int = 100,
    offset: int = 0,
    somente_bloqueados: bool = False,
    dispositivo: Optional[str] = None,
    desde: Optional[datetime] = None,
) -> dict:
    limite = max(1, min(limite, 500))
    itens, total = svc.listar_eventos(
        session,
        limite=limite,
        offset=max(0, offset),
        somente_bloqueados=somente_bloqueados,
        dispositivo=dispositivo,
        desde=desde,
    )
    return {
        "items": [_para_out(e).model_dump() for e in itens],
        "total": total,
        "limit": limite,
        "offset": max(0, offset),
    }


@router.get("/resumo")
def ver_resumo(session: SessionDep, user: CurrentUser, dias: int = 7) -> dict:
    return svc.resumo(session, dias=max(1, min(dias, 90)))


@router.get("/config", response_model=ConfigOut)
def ver_config(session: SessionDep, user: CurrentUser) -> ConfigOut:
    cfg = svc.get_config(session)
    return ConfigOut(
        ativo=cfg.ativo,
        sensibilidade=cfg.sensibilidade,
        retencao_dias=cfg.retencao_dias,
        token_ingestao=cfg.token_ingestao,
        pin_definido=bool(cfg.pin_hash),
    )


@router.patch("/config", response_model=ConfigOut)
def editar_config(payload: ConfigPatch, session: SessionDep, user: CurrentUser) -> ConfigOut:
    cfg = svc.get_config(session)
    if payload.sensibilidade is not None:
        if payload.sensibilidade not in svc.SENSIBILIDADES:
            raise HTTPException(400, f"sensibilidade deve ser uma de {list(svc.SENSIBILIDADES)}")
        cfg.sensibilidade = payload.sensibilidade
    if payload.ativo is not None:
        cfg.ativo = payload.ativo
    if payload.retencao_dias is not None:
        cfg.retencao_dias = payload.retencao_dias
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return ConfigOut(
        ativo=cfg.ativo,
        sensibilidade=cfg.sensibilidade,
        retencao_dias=cfg.retencao_dias,
        token_ingestao=cfg.token_ingestao,
        pin_definido=bool(cfg.pin_hash),
    )


def _exige_pin_liberado(session) -> None:
    """Barra a tentativa antes de comparar o PIN, se estiver em lockout."""
    faltam = svc.pin_bloqueado_por(session)
    if faltam is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Muitas tentativas de PIN. Tente de novo em {faltam}s.",
            headers={"Retry-After": str(faltam)},
        )


@router.post("/config/pin")
def definir_pin(payload: PinIn, session: SessionDep, user: CurrentUser) -> dict:
    """Define ou troca o PIN. Trocar exige o PIN atual — senao bastaria roubar a
    sessao aberta do responsavel para desarmar a trava. A troca conta para o
    mesmo lockout da verificacao: senao ela viraria o oraculo de forca bruta."""
    if not payload.pin.isdigit():
        raise HTTPException(400, "PIN deve conter apenas digitos")
    cfg = svc.get_config(session)
    if cfg.pin_hash:
        _exige_pin_liberado(session)
        if not (payload.pin_atual and verify_password(payload.pin_atual, cfg.pin_hash)):
            svc.registrar_falha_de_pin(session)
            raise HTTPException(status.HTTP_403_FORBIDDEN, "PIN atual incorreto")
        svc.limpar_falhas_de_pin(session)
    cfg = svc.get_config(session)
    cfg.pin_hash = hash_password(payload.pin)
    session.add(cfg)
    session.commit()
    return {"pin_definido": True}


@router.post("/config/pin/verificar")
def verificar_pin(payload: PinCheck, session: SessionDep, user: CurrentUser) -> dict:
    cfg = svc.get_config(session)
    if not cfg.pin_hash:
        raise HTTPException(400, "Nenhum PIN definido")
    _exige_pin_liberado(session)
    ok = verify_password(payload.pin, cfg.pin_hash)
    if ok:
        svc.limpar_falhas_de_pin(session)
    else:
        svc.registrar_falha_de_pin(session)
        # A tentativa falha vira evento: o responsavel ve quem tentou desarmar.
        svc.registrar_evento(
            session,
            busca="tentativa de desligar o Sentinela com PIN incorreto",
            origem="painel",
            tema="Burlar protecao",
            confianca=1.0,
            bloqueado=True,
        )
    return {"ok": ok}


@router.post("/token/rotacionar", response_model=ConfigOut)
def rotacionar(session: SessionDep, user: CurrentUser) -> ConfigOut:
    cfg = svc.rotacionar_token(session)
    return ConfigOut(
        ativo=cfg.ativo,
        sensibilidade=cfg.sensibilidade,
        retencao_dias=cfg.retencao_dias,
        token_ingestao=cfg.token_ingestao,
        pin_definido=bool(cfg.pin_hash),
    )


@router.post("/importar")
def importar_jsonl(payload: dict, session: SessionDep, user: CurrentUser) -> dict:
    """Importa o `supervisao.jsonl` legado (app PowerShell / botao Exportar da
    extensao). Mantem vivo o caminho antigo: nada do que ja existe se perde.

    Corpo: {"conteudo": "<linhas jsonl>"}. Linhas invalidas sao puladas e
    contadas — importacao parcial e melhor que erro total.
    """
    conteudo = (payload or {}).get("conteudo") or ""
    if not isinstance(conteudo, str) or not conteudo.strip():
        raise HTTPException(400, "Envie 'conteudo' com o texto do arquivo .jsonl")

    importados = 0
    ignorados = 0
    for linha in conteudo.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            obj = json.loads(linha)
        except (ValueError, TypeError):
            ignorados += 1
            continue
        if not isinstance(obj, dict):
            ignorados += 1
            continue
        quando = None
        if obj.get("hora"):
            try:
                quando = datetime.fromisoformat(str(obj["hora"]).replace("Z", "+00:00"))
            except ValueError:
                quando = None
        try:
            # Mesma validacao da ingestao ao vivo (svc.normalizar_evento):
            # linha sem texto de busca cai aqui como ignorada, nao entra torta.
            svc.registrar_evento(
                session,
                busca=str(obj.get("busca") or ""),
                origem=str(obj.get("origem") or "importado"),
                dispositivo=str(obj.get("dispositivo") or "este-pc"),
                tema=obj.get("tema"),
                confianca=float(obj.get("confianca") or 0.0),
                bloqueado=bool(obj.get("bloqueado")),
                ocorrido_em=quando,
                commit=False,
            )
        except (ValueError, TypeError):
            ignorados += 1
            continue
        importados += 1
    session.commit()
    return {"importados": importados, "ignorados": ignorados}
