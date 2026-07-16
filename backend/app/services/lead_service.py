"""Lead → Contact/Company/Opportunity conversion flow."""
from datetime import datetime, timezone
from uuid import UUID
from sqlmodel import Session, select

from app.models import Company, Contact, Lead, LeadStatus, Opportunity, Pipeline
from app.schemas.crm import LeadConvertRequest, LeadConvertResponse
from app.services import pipeline_service
from app.services.activity_service import log_activity


def convert_lead(
    session: Session,
    *,
    workspace_id: UUID,
    actor_user_id: UUID,
    lead: Lead,
    req: LeadConvertRequest,
) -> LeadConvertResponse:
    if lead.status == LeadStatus.converted:
        raise ValueError("lead_already_converted")

    # Validate caller-supplied FKs actually belong to this workspace. Without
    # this, a client could pass a foreign workspace's UUID and end up with an
    # opportunity referencing data outside the caller's tenant. The DB FK
    # constraint doesn't enforce tenant scoping — that's the app's job.
    company_id: UUID | None = req.company_id
    if company_id is not None:
        exists = session.exec(
            select(Company.id).where(
                Company.id == company_id,
                Company.workspace_id == workspace_id,
                Company.deleted_at.is_(None),
            )
        ).first()
        if exists is None:
            raise ValueError("company_not_in_workspace")

    if req.pipeline_id is not None:
        exists = session.exec(
            select(Pipeline.id).where(
                Pipeline.id == req.pipeline_id,
                Pipeline.workspace_id == workspace_id,
                Pipeline.deleted_at.is_(None),
            )
        ).first()
        if exists is None:
            raise ValueError("pipeline_not_in_workspace")

    if req.create_company and not company_id and lead.company_name:
        company = Company(workspace_id=workspace_id, name=lead.company_name, owner_user_id=actor_user_id)
        session.add(company)
        session.flush()
        company_id = company.id

    contact = Contact(
        workspace_id=workspace_id,
        first_name=lead.first_name,
        last_name=lead.last_name,
        email=lead.email,
        phone=lead.phone,
        company_id=company_id,
        owner_user_id=actor_user_id,
    )
    session.add(contact)
    session.flush()

    opportunity_id: UUID | None = None
    if req.create_opportunity:
        pipeline_id = req.pipeline_id
        if pipeline_id is None:
            pipeline_id = pipeline_service.get_default_pipeline(session, workspace_id).id
        stage = pipeline_service.first_stage(session, workspace_id, pipeline_id)
        if stage is None:
            raise ValueError("pipeline_has_no_stages")
        name = req.opportunity_name or f"Opportunity — {lead.first_name} {lead.last_name or ''}".strip(" —")
        opp = Opportunity(
            workspace_id=workspace_id,
            name=name,
            pipeline_id=pipeline_id,
            stage_id=stage.id,
            amount=req.amount,
            currency=req.currency,
            contact_id=contact.id,
            company_id=company_id,
            expected_close_date=req.expected_close_date,
            probability=stage.probability,
            owner_user_id=actor_user_id,
        )
        session.add(opp)
        session.flush()
        opportunity_id = opp.id

    lead.status = LeadStatus.converted
    lead.converted_at = datetime.now(timezone.utc)
    lead.converted_contact_id = contact.id
    lead.converted_opportunity_id = opportunity_id
    session.add(lead)

    log_activity(
        session,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        kind="lead_converted",
        subject_type="lead",
        subject_id=lead.id,
        summary=f"Converted → contact {contact.id}",
        data={
            "contact_id": str(contact.id),
            "company_id": str(company_id) if company_id else None,
            "opportunity_id": str(opportunity_id) if opportunity_id else None,
        },
        commit=False,
    )
    session.commit()
    return LeadConvertResponse(
        lead_id=lead.id,
        contact_id=contact.id,
        company_id=company_id,
        opportunity_id=opportunity_id,
    )
