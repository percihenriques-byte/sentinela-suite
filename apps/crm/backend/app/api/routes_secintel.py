"""API do modulo Seguranca (`/seguranca`).

TODAS as rotas exigem o papel "responsavel" (owner/admin do workspace) — ver
`CurrentResponsavel` em deps e ESPEC-SEGURANCA.md secao 5. Acoes sensiveis
gravam `sec_auditoria`.
"""
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentResponsavel, CurrentUser, SessionDep
from app.models.secintel import SecIncidenteEstado
from app.schemas.secintel import (
    ItemOut,
    AssetCreate,
    AssetOut,
    AssetUpdate,
    AuditoriaOut,
    FonteOut,
    IncidenteDetalheOut,
    IncidenteOut,
    RecomendacaoPatch,
    TransicaoIn,
)
from app.services import secintel_service as svc

router = APIRouter(prefix="/seguranca", tags=["seguranca"])


# ---- fontes / auditoria ----

@router.get("/fontes", response_model=list[FonteOut])
def listar_fontes(
    session: SessionDep, user: CurrentUser, ws: CurrentResponsavel
) -> list[FonteOut]:
    fontes = svc.garantir_fontes(session)
    return [FonteOut.model_validate(f, from_attributes=True) for f in fontes]


@router.get("/auditoria", response_model=list[AuditoriaOut])
def listar_auditoria(
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentResponsavel,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[AuditoriaOut]:
    linhas = svc.listar_auditoria(session, ws.id, limit=limit, offset=offset)
    return [AuditoriaOut.model_validate(l, from_attributes=True) for l in linhas]


# ---- ativos (M1) ----

@router.get("/ativos", response_model=list[AssetOut])
def listar_ativos(
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentResponsavel,
    incluir_arquivados: bool = Query(False),
) -> list[AssetOut]:
    ativos = svc.listar_assets(session, ws.id, incluir_arquivados=incluir_arquivados)
    return [AssetOut.model_validate(a, from_attributes=True) for a in ativos]


@router.post("/ativos", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
def criar_ativo(
    payload: AssetCreate, session: SessionDep, user: CurrentUser, ws: CurrentResponsavel
) -> AssetOut:
    asset = svc.criar_asset(
        session, ws.id, user, payload.tipo, payload.identificador, payload.titular
    )
    svc.registrar_auditoria(
        session, ws.id, user.id, "ativo_criado",
        {"asset_id": str(asset.id), "tipo": asset.tipo.value},
    )
    return AssetOut.model_validate(asset, from_attributes=True)


@router.patch("/ativos/{asset_id}", response_model=AssetOut)
def editar_ativo(
    asset_id: UUID,
    payload: AssetUpdate,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentResponsavel,
) -> AssetOut:
    asset = svc.editar_asset(session, ws.id, asset_id, payload.titular)
    return AssetOut.model_validate(asset, from_attributes=True)


@router.delete("/ativos/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def arquivar_ativo(
    asset_id: UUID, session: SessionDep, user: CurrentUser, ws: CurrentResponsavel
) -> None:
    svc.arquivar_asset(session, ws.id, asset_id)
    svc.registrar_auditoria(
        session, ws.id, user.id, "ativo_arquivado", {"asset_id": str(asset_id)}
    )


@router.post("/ativos/{asset_id}/verificar", response_model=AssetOut)
def verificar_ativo(
    asset_id: UUID, session: SessionDep, user: CurrentUser, ws: CurrentResponsavel
) -> AssetOut:
    asset = svc.verificar_posse(session, ws.id, user, asset_id)
    svc.registrar_auditoria(
        session, ws.id, user.id, "ativo_verificado",
        {"asset_id": str(asset_id), "nivel": asset.nivel_autorizacao.value},
    )
    return AssetOut.model_validate(asset, from_attributes=True)


# ---- incidentes + correlacao (M2) ----

@router.get("/incidentes", response_model=list[IncidenteOut])
def listar_incidentes(
    session: SessionDep, user: CurrentUser, ws: CurrentResponsavel,
    estado: SecIncidenteEstado | None = Query(None),
) -> list[IncidenteOut]:
    incs = svc.listar_incidentes(session, ws.id, estado=estado)
    return [IncidenteOut.model_validate(i, from_attributes=True) for i in incs]


@router.get("/incidentes/{incidente_id}", response_model=IncidenteDetalheOut)
def detalhe_incidente(
    incidente_id: UUID, session: SessionDep, user: CurrentUser, ws: CurrentResponsavel,
) -> IncidenteDetalheOut:
    import json

    inc = svc.get_incidente(session, ws.id, incidente_id)
    itens = svc.itens_do_incidente(session, incidente_id)
    base = IncidenteOut.model_validate(inc, from_attributes=True).model_dump()
    return IncidenteDetalheOut(
        **base,
        recomendacoes=json.loads(inc.recomendacoes or "[]"),
        itens=[ItemOut.model_validate(i, from_attributes=True) for i in itens],
    )


@router.patch("/incidentes/{incidente_id}/estado", response_model=IncidenteOut)
def transicionar_incidente(
    incidente_id: UUID, payload: TransicaoIn,
    session: SessionDep, user: CurrentUser, ws: CurrentResponsavel,
) -> IncidenteOut:
    inc = svc.transicionar(session, ws.id, user.id, incidente_id, payload.estado)
    return IncidenteOut.model_validate(inc, from_attributes=True)


@router.patch("/incidentes/{incidente_id}/recomendacoes/{indice}", response_model=IncidenteDetalheOut)
def marcar_recomendacao(
    incidente_id: UUID, indice: int, payload: RecomendacaoPatch,
    session: SessionDep, user: CurrentUser, ws: CurrentResponsavel,
) -> IncidenteDetalheOut:
    import json

    inc = svc.marcar_recomendacao(session, ws.id, incidente_id, indice, payload.feito)
    itens = svc.itens_do_incidente(session, incidente_id)
    base = IncidenteOut.model_validate(inc, from_attributes=True).model_dump()
    return IncidenteDetalheOut(
        **base, recomendacoes=json.loads(inc.recomendacoes or "[]"),
        itens=[ItemOut.model_validate(i, from_attributes=True) for i in itens],
    )


@router.post("/varreduras/correlacao", response_model=list[IncidenteOut])
def rodar_correlacao(
    session: SessionDep, user: CurrentUser, ws: CurrentResponsavel,
) -> list[IncidenteOut]:
    incs = svc.correlacionar(session, ws.id)
    return [IncidenteOut.model_validate(i, from_attributes=True) for i in incs]


# ---- achados + visao geral (M3) ----
from app.models.secintel import SecAchadoStatus, SecSeveridade  # noqa: E402
from app.schemas.secintel import (  # noqa: E402
    AchadoOut,
    FalsoPositivoIn,
    VisaoGeralOut,
)


@router.get("/visao-geral", response_model=VisaoGeralOut)
def visao_geral(session: SessionDep, user: CurrentUser, ws: CurrentResponsavel) -> VisaoGeralOut:
    return VisaoGeralOut(**svc.visao_geral(session, ws.id))


@router.get("/achados", response_model=list[AchadoOut])
def listar_achados(
    session: SessionDep, user: CurrentUser, ws: CurrentResponsavel,
    status_f: SecAchadoStatus | None = Query(None, alias="status"),
    severidade: SecSeveridade | None = Query(None),
    fonte: str | None = Query(None),
) -> list[AchadoOut]:
    achados = svc.listar_achados(session, ws.id, status_f=status_f, severidade=severidade, fonte=fonte)
    return [AchadoOut.model_validate(a, from_attributes=True) for a in achados]


@router.patch("/achados/{achado_id}/falso-positivo", response_model=AchadoOut)
def marcar_fp(
    achado_id: UUID, payload: FalsoPositivoIn,
    session: SessionDep, user: CurrentUser, ws: CurrentResponsavel,
) -> AchadoOut:
    a = svc.marcar_falso_positivo(session, ws.id, user.id, achado_id, payload.motivo)
    return AchadoOut.model_validate(a, from_attributes=True)


@router.patch("/achados/{achado_id}/resolver", response_model=AchadoOut)
def resolver(
    achado_id: UUID, session: SessionDep, user: CurrentUser, ws: CurrentResponsavel,
) -> AchadoOut:
    a = svc.marcar_resolvido(session, ws.id, user.id, achado_id)
    return AchadoOut.model_validate(a, from_attributes=True)


# ---- consentimento de fontes + varredura de exposicao (M4) ----
from pydantic import BaseModel  # noqa: E402


class _FontePatch(BaseModel):
    habilitada: bool


@router.patch("/fontes/{nome}", response_model=FonteOut)
def alternar_fonte(
    nome: str, payload: _FontePatch,
    session: SessionDep, user: CurrentUser, ws: CurrentResponsavel,
) -> FonteOut:
    f = svc.alternar_fonte(session, ws.id, user.id, nome, payload.habilitada)
    return FonteOut.model_validate(f, from_attributes=True)


@router.post("/varreduras/exposicao", response_model=list[AchadoOut])
def rodar_exposicao(
    session: SessionDep, user: CurrentUser, ws: CurrentResponsavel,
) -> list[AchadoOut]:
    achados = svc.rodar_exposicao(session, ws.id)
    return [AchadoOut.model_validate(a, from_attributes=True) for a in achados]
