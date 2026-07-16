from uuid import UUID
from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, CurrentWorkspace, SessionDep
from app.models import Pipeline, PipelineStage
from app.schemas.crm import PipelineRead, PipelineStageRead
from app.services import crud, pipeline_service

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


# Ready-to-install pipeline templates
PIPELINE_TEMPLATES = {
    "saas": {
        "name": "SaaS B2B",
        "description": "Sales pipeline para produtos SaaS B2B",
        "stages": [
            {"name": "Trial signup", "probability": 5},
            {"name": "Product demo", "probability": 20},
            {"name": "Proposta", "probability": 40},
            {"name": "Negociação", "probability": 70},
            {"name": "Fechado — Won", "probability": 100, "is_won": True},
            {"name": "Fechado — Lost", "probability": 0, "is_lost": True},
        ],
    },
    "consulting": {
        "name": "Consultoria",
        "description": "Pipeline para projetos de consultoria",
        "stages": [
            {"name": "Discovery call", "probability": 10},
            {"name": "Escopo definido", "probability": 30},
            {"name": "Proposta enviada", "probability": 50},
            {"name": "Contratado", "probability": 100, "is_won": True},
            {"name": "Recusado", "probability": 0, "is_lost": True},
        ],
    },
    "agency": {
        "name": "Agência criativa",
        "description": "Pipeline para agências de marketing/design",
        "stages": [
            {"name": "Briefing", "probability": 10},
            {"name": "Orçamento", "probability": 25},
            {"name": "Apresentação", "probability": 50},
            {"name": "Aprovação", "probability": 80},
            {"name": "Won", "probability": 100, "is_won": True},
            {"name": "Lost", "probability": 0, "is_lost": True},
        ],
    },
    "realestate": {
        "name": "Imobiliária",
        "description": "Pipeline para vendas imobiliárias",
        "stages": [
            {"name": "Lead qualificado", "probability": 10},
            {"name": "Visita agendada", "probability": 30},
            {"name": "Proposta", "probability": 60},
            {"name": "Contrato", "probability": 90},
            {"name": "Escritura", "probability": 100, "is_won": True},
            {"name": "Desistiu", "probability": 0, "is_lost": True},
        ],
    },
}


@router.get("/templates")
def list_pipeline_templates() -> dict:
    """Ready-to-install pipeline presets."""
    return {"templates": [{"key": k, **v} for k, v in PIPELINE_TEMPLATES.items()]}


@router.post("/from-template/{template_key}", response_model=PipelineRead, status_code=status.HTTP_201_CREATED)
def create_from_template(
    template_key: str,
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
) -> PipelineRead:
    tpl = PIPELINE_TEMPLATES.get(template_key)
    if not tpl:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"template '{template_key}' not found")
    # Create pipeline (not default — the user already has one)
    p = Pipeline(workspace_id=ws.id, name=tpl["name"], description=tpl["description"], is_default=False)
    session.add(p)
    session.flush()
    for i, stage_def in enumerate(tpl["stages"]):
        stage = PipelineStage(
            workspace_id=ws.id,
            pipeline_id=p.id,
            name=stage_def["name"],
            order_index=i,
            probability=stage_def.get("probability", 0),
            is_won=stage_def.get("is_won", False),
            is_lost=stage_def.get("is_lost", False),
        )
        session.add(stage)
    session.commit()
    session.refresh(p)
    stages = pipeline_service.get_stages(session, ws.id, p.id)
    return PipelineRead(
        id=p.id, name=p.name, description=p.description, is_default=p.is_default,
        stages=[PipelineStageRead.model_validate(s) for s in stages],
    )


@router.get("", response_model=list[PipelineRead])
def list_pipelines(session: SessionDep, _user: CurrentUser, ws: CurrentWorkspace) -> list[PipelineRead]:
    # Ensure a default pipeline exists so the UI always has something to show.
    pipeline_service.get_default_pipeline(session, ws.id)
    pipelines = list(session.exec(crud.scoped_query(Pipeline, ws.id).order_by(Pipeline.created_at.asc())).all())
    result: list[PipelineRead] = []
    for p in pipelines:
        stages = pipeline_service.get_stages(session, ws.id, p.id)
        result.append(PipelineRead(
            id=p.id,
            name=p.name,
            description=p.description,
            is_default=p.is_default,
            stages=[PipelineStageRead.model_validate(s) for s in stages],
        ))
    return result


@router.get("/{pipeline_id}", response_model=PipelineRead)
def get_pipeline(pipeline_id: UUID, session: SessionDep, _user: CurrentUser, ws: CurrentWorkspace) -> PipelineRead:
    p = crud.get_or_404(session, Pipeline, ws.id, pipeline_id)
    stages = pipeline_service.get_stages(session, ws.id, p.id)
    return PipelineRead(
        id=p.id,
        name=p.name,
        description=p.description,
        is_default=p.is_default,
        stages=[PipelineStageRead.model_validate(s) for s in stages],
    )
