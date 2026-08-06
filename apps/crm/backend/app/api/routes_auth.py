from fastapi import APIRouter, HTTPException, status
from jose import JWTError

from app.api.deps import SessionDep, CurrentUser
from app.core.security import decode_token, create_access_token, create_refresh_token
from app.schemas.auth import RegisterRequest, LoginRequest, TokenPair, RefreshRequest, UserPublic
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, session: SessionDep) -> TokenPair:
    try:
        _, _, tokens = auth_service.register(session, req)
    except ValueError as e:
        if str(e) == "email_taken":
            raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered") from None
        raise
    return tokens


@router.post("/login", response_model=TokenPair)
def login(req: LoginRequest, session: SessionDep) -> TokenPair:
    try:
        _, tokens = auth_service.login(session, req)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials") from None
    return tokens


@router.post("/refresh", response_model=TokenPair)
def refresh(req: RefreshRequest) -> TokenPair:
    try:
        payload = decode_token(req.refresh_token)
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token") from None
    if payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong token type")
    subject = payload.get("sub")
    if not subject:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed token")
    return TokenPair(
        access_token=create_access_token(subject),
        refresh_token=create_refresh_token(subject),
    )


@router.get("/me", response_model=UserPublic)
def me(user: CurrentUser) -> UserPublic:
    return UserPublic(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
    )
