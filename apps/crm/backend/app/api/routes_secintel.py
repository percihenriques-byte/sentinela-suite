"""API do modulo Seguranca (`/seguranca`).

TODAS as rotas exigem o papel "responsavel" (owner/admin do workspace) — ver
`CurrentResponsavel` em deps e ESPEC-SEGURANCA.md secao 5. Acoes sensiveis
gravam `sec_auditoria`.
"""
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentResponsavel, CurrentUser, SessionDep
from app.schemas.secintel import (
    AssetCreate,
    AssetOut,
    AssetUpdate,
    AuditoriaOut,
    FonteOut,
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
