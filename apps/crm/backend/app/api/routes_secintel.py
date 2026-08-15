"""API do modulo Seguranca (`/seguranca`) — M0.

Superficie minima deste marco: listar fontes (com a descricao do que sai da
maquina) e ler a trilha de auditoria. TODAS as rotas exigem o papel
"responsavel" (owner/admin do workspace) — ver `CurrentResponsavel` em deps e
ESPEC-SEGURANCA.md secao 5. As demais rotas chegam nos marcos M1+.
"""
from fastapi import APIRouter

from app.api.deps import CurrentResponsavel, CurrentUser, SessionDep
from app.schemas.secintel import AuditoriaOut, FonteOut
from app.services import secintel_service as svc

router = APIRouter(prefix="/seguranca", tags=["seguranca"])


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
    limit: int = 50,
    offset: int = 0,
) -> list[AuditoriaOut]:
    linhas = svc.listar_auditoria(session, ws.id, limit=limit, offset=offset)
    return [AuditoriaOut.model_validate(l, from_attributes=True) for l in linhas]
