"""External accounts (OAuth) — plumbing only.

No live network calls. Callers post an already-obtained token; we encrypt-at-
rest via Fernet and store the metadata. Future providers plug into this shape.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.api.deps import CurrentUser, CurrentWorkspace, SessionDep
from app.core.crypto import decrypt, encrypt
from app.models import ExternalAccount
from app.schemas.common import Page
from app.services import crud

router = APIRouter(prefix="/integrations", tags=["integrations"])


SUPPORTED_PROVIDERS = {"google", "microsoft", "slack", "manual"}


class ConnectRequest(BaseModel):
    provider: str
    access_token: str
    refresh_token: Optional[str] = None
    account_label: Optional[str] = None
    scopes: Optional[str] = None
    token_type: str = "bearer"
    expires_at: Optional[datetime] = None


class ExternalAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    provider: str
    account_label: Optional[str] = None
    scopes: Optional[str] = None
    token_type: str
    expires_at: Optional[datetime] = None
    is_active: bool


@router.post("/connect", response_model=ExternalAccountRead, status_code=status.HTTP_201_CREATED)
def connect(payload: ConnectRequest, session: SessionDep, user: CurrentUser, ws: CurrentWorkspace) -> ExternalAccount:
    if payload.provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(400, f"provider must be one of {sorted(SUPPORTED_PROVIDERS)}")
    try:
        access_enc = encrypt(payload.access_token)
        refresh_enc = encrypt(payload.refresh_token) if payload.refresh_token else None
    except RuntimeError as e:
        raise HTTPException(500, str(e)) from None
    acc = ExternalAccount(
        workspace_id=ws.id, user_id=user.id,
        provider=payload.provider, account_label=payload.account_label,
        scopes=payload.scopes,
        access_token_enc=access_enc, refresh_token_enc=refresh_enc,
        token_type=payload.token_type, expires_at=payload.expires_at,
    )
    return crud.create_scoped(session, acc)


@router.get("", response_model=Page[ExternalAccountRead])
def list_accounts(session: SessionDep, _user: CurrentUser, ws: CurrentWorkspace) -> Page[ExternalAccountRead]:
    base = crud.scoped_query(ExternalAccount, ws.id)
    total = crud.count_from(session, base)
    rows = session.exec(base.order_by(ExternalAccount.created_at.desc())).all()
    return Page[ExternalAccountRead].build([ExternalAccountRead.model_validate(r) for r in rows], total, 50, 0)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def disconnect(account_id: UUID, session: SessionDep, _user: CurrentUser, ws: CurrentWorkspace) -> None:
    acc = crud.get_or_404(session, ExternalAccount, ws.id, account_id)
    crud.soft_delete(session, acc)


@router.get("/{account_id}/token", response_model=dict)
def peek_token(account_id: UUID, session: SessionDep, _user: CurrentUser, ws: CurrentWorkspace) -> dict:
    """Diagnostic: returns whether the stored token decrypts. Never returns the token itself."""
    acc = crud.get_or_404(session, ExternalAccount, ws.id, account_id)
    try:
        plain = decrypt(acc.access_token_enc)
    except RuntimeError as e:
        raise HTTPException(500, str(e)) from None
    return {"decryptable": bool(plain), "length": len(plain), "provider": acc.provider}
