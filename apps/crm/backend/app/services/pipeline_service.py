"""Pipeline bootstrap + lookup helpers.

Every workspace needs at least one pipeline for opportunities to live in.
We create a sensible default on-demand so users don't have to configure
anything before creating their first opportunity.
"""
from typing import Iterable
from uuid import UUID
from sqlmodel import Session, select

from app.models import Pipeline, PipelineStage


DEFAULT_STAGES: tuple[tuple[str, float, bool, bool], ...] = (
    # (name, probability%, is_won, is_lost)
    ("Prospecting", 10.0, False, False),
    ("Qualification", 25.0, False, False),
    ("Proposal", 50.0, False, False),
    ("Negotiation", 75.0, False, False),
    ("Won", 100.0, True, False),
    ("Lost", 0.0, False, True),
)


def get_default_pipeline(session: Session, workspace_id: UUID) -> Pipeline:
    """Return the workspace's default pipeline, creating one if missing."""
    stmt = (
        select(Pipeline)
        .where(
            Pipeline.workspace_id == workspace_id,
            Pipeline.deleted_at.is_(None),
            Pipeline.is_default.is_(True),
        )
        .limit(1)
    )
    pipeline = session.exec(stmt).first()
    if pipeline:
        return pipeline

    # Also honor any existing non-default pipeline before creating a new one.
    fallback_stmt = (
        select(Pipeline)
        .where(Pipeline.workspace_id == workspace_id, Pipeline.deleted_at.is_(None))
        .order_by(Pipeline.created_at.asc())
        .limit(1)
    )
    fallback = session.exec(fallback_stmt).first()
    if fallback:
        return fallback

    pipeline = Pipeline(
        workspace_id=workspace_id,
        name="Sales Pipeline",
        description="Default sales pipeline created automatically.",
        is_default=True,
    )
    session.add(pipeline)
    session.flush()

    for index, (name, prob, is_won, is_lost) in enumerate(DEFAULT_STAGES):
        session.add(PipelineStage(
            workspace_id=workspace_id,
            pipeline_id=pipeline.id,
            name=name,
            order_index=index,
            probability=prob,
            is_won=is_won,
            is_lost=is_lost,
        ))
    session.commit()
    session.refresh(pipeline)
    return pipeline


def get_stages(session: Session, workspace_id: UUID, pipeline_id: UUID) -> list[PipelineStage]:
    stmt = (
        select(PipelineStage)
        .where(
            PipelineStage.workspace_id == workspace_id,
            PipelineStage.pipeline_id == pipeline_id,
            PipelineStage.deleted_at.is_(None),
        )
        .order_by(PipelineStage.order_index.asc())
    )
    return list(session.exec(stmt).all())


def first_stage(session: Session, workspace_id: UUID, pipeline_id: UUID) -> PipelineStage | None:
    stages = get_stages(session, workspace_id, pipeline_id)
    return stages[0] if stages else None


def resolve_stage(
    session: Session,
    workspace_id: UUID,
    pipeline_id: UUID,
    stage_id: UUID | None,
) -> PipelineStage:
    if stage_id is not None:
        stmt = select(PipelineStage).where(
            PipelineStage.workspace_id == workspace_id,
            PipelineStage.pipeline_id == pipeline_id,
            PipelineStage.id == stage_id,
            PipelineStage.deleted_at.is_(None),
        )
        stage = session.exec(stmt).first()
        if stage is None:
            raise ValueError("stage_not_in_pipeline")
        return stage
    stage = first_stage(session, workspace_id, pipeline_id)
    if stage is None:
        raise ValueError("pipeline_has_no_stages")
    return stage
