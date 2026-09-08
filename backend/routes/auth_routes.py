from fastapi import APIRouter, Request, Response, HTTPException, status, Header
from pydantic import BaseModel, Field
from typing import Optional
import uuid

from backend.config import settings
from backend.security import limiter
from backend.auth import (
    verify_password_constant_time,
    create_access_token,
    create_refresh_token,
    generate_csrf_token,
    verify_refresh_token,
    revoke_token,
    hash_password,
    verify_password,
    get_user_by_username,
)
from backend.logger import event_broker
from backend.db import User, engine
from sqlmodel import Session

router = APIRouter(prefix="/auth", tags=["Authentication"])


class VerifyPasswordRequest(BaseModel):
    password: str = Field(description="Admin access password")


class AuthResponse(BaseModel):
    access_token: str
    csrf_token: str
    token_type: str = "bearer"
    expires_in: int


class RegisterRequest(BaseModel):
    username: str = Field(description="Unique username", min_length=3, max_length=50)
    email: Optional[str] = Field(default=None, description="Email address")
    password: str = Field(description="Password", min_length=6)


class LoginRequest(BaseModel):
    username_or_email: str = Field(description="Username or email")
    password: str = Field(description="Password")


class UserResponse(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    is_active: bool = True


class AuthResponseWithUser(AuthResponse):
    user: UserResponse


@router.post("/verify", response_model=AuthResponse)
@limiter.limit("5/minute")
async def verify_password(request: Request, body: VerifyPasswordRequest, response: Response):
    client_ip = request.client.host if request.client else "unknown"
    is_valid = verify_password_constant_time(body.password)

    if not is_valid:
        event_broker.log_audit(
            event_type="auth_verify",
            actor_ip=client_ip,
            details="Failed password attempt",
            status="failure",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access password.",
        )

    access_token = create_access_token()
    refresh_token, jti = create_refresh_token()
    csrf_token = generate_csrf_token()

    response.set_cookie(
        key="forge_refresh_token",
        value=refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_HOURS * 3600,
        path="/auth",
    )
    response.set_cookie(
        key="forge_csrf_token",
        value=csrf_token,
        httponly=False,
        secure=not settings.DEBUG,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_HOURS * 3600,
        path="/",
    )

    event_broker.log_audit(
        event_type="auth_verify",
        actor_ip=client_ip,
        details="Successful login",
        status="success",
    )

    return AuthResponse(
        access_token=access_token,
        csrf_token=csrf_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/register", response_model=AuthResponseWithUser)
@limiter.limit("5/minute")
async def register_user(request: Request, body: RegisterRequest, response: Response):
    client_ip = request.client.host if request.client else "unknown"

    existing = get_user_by_username(body.username)
    if existing:
        event_broker.log_audit(
            event_type="auth_register",
            actor_ip=client_ip,
            details="Username already exists: " + body.username,
            status="failure",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered.",
        )

    user_id = str(uuid.uuid4())[:8]
    hashed_pw = hash_password(body.password)
    new_user = User(
        id=user_id,
        username=body.username,
        email=body.email,
        hashed_password=hashed_pw,
    )

    with Session(engine) as session:
        session.add(new_user)
        session.commit()
        session.refresh(new_user)

    access_token = create_access_token(subject=user_id)
    refresh_token, jti = create_refresh_token(subject=user_id)
    csrf_token = generate_csrf_token()

    response.set_cookie(
        key="forge_refresh_token",
        value=refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_HOURS * 3600,
        path="/auth",
    )
    response.set_cookie(
        key="forge_csrf_token",
        value=csrf_token,
        httponly=False,
        secure=not settings.DEBUG,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_HOURS * 3600,
        path="/",
    )

    event_broker.log_audit(
        event_type="auth_register",
        actor_ip=client_ip,
        details="New user registered: " + body.username,
        status="success",
    )

    return AuthResponseWithUser(
        access_token=access_token,
        csrf_token=csrf_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(
            id=user_id,
            username=new_user.username,
            email=new_user.email,
            is_active=new_user.is_active,
        ),
    )


@router.post("/login", response_model=AuthResponseWithUser)
@limiter.limit("10/minute")
async def login_user(request: Request, body: LoginRequest, response: Response):
    client_ip = request.client.host if request.client else "unknown"

    user = get_user_by_username(body.username_or_email)
    if not user or not user.get("is_active"):
        event_broker.log_audit(
            event_type="auth_login",
            actor_ip=client_ip,
            details="Login failed: user not found or inactive (" + body.username_or_email + ")",
            status="failure",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    if not verify_password(body.password, user["hashed_password"]):
        event_broker.log_audit(
            event_type="auth_login",
            actor_ip=client_ip,
            details="Login failed: wrong password for " + body.username_or_email,
            status="failure",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    access_token = create_access_token(subject=user["id"])
    refresh_token, jti = create_refresh_token(subject=user["id"])
    csrf_token = generate_csrf_token()

    response.set_cookie(
        key="forge_refresh_token",
        value=refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_HOURS * 3600,
        path="/auth",
    )
    response.set_cookie(
        key="forge_csrf_token",
        value=csrf_token,
        httponly=False,
        secure=not settings.DEBUG,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_HOURS * 3600,
        path="/",
    )

    event_broker.log_audit(
        event_type="auth_login",
        actor_ip=client_ip,
        details="Successful login: " + user["username"],
        status="success",
    )

    return AuthResponseWithUser(
        access_token=access_token,
        csrf_token=csrf_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(
            id=user["id"],
            username=user["username"],
            email=user["email"],
            is_active=user["is_active"],
        ),
    )


@router.post("/refresh", response_model=AuthResponse)
@limiter.limit("20/minute")
async def refresh_access_token(
    request: Request,
    response: Response,
    x_csrf_token: Optional[str] = Header(None, alias="X-CSRF-Token"),
):
    client_ip = request.client.host if request.client else "unknown"
    refresh_cookie = request.cookies.get("forge_refresh_token")
    csrf_cookie = request.cookies.get("forge_csrf_token")

    if not refresh_cookie:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh cookie.",
        )

    if not x_csrf_token or not csrf_cookie or x_csrf_token != csrf_cookie:
        event_broker.log_audit(
            event_type="auth_refresh",
            actor_ip=client_ip,
            details="CSRF token mismatch on refresh",
            status="blocked",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF verification failed.",
        )

    payload = verify_refresh_token(refresh_cookie)
    old_jti = payload.get("jti")

    if old_jti:
        revoke_token(old_jti)

    access_token = create_access_token()
    new_refresh_token, new_jti = create_refresh_token()
    new_csrf_token = generate_csrf_token()

    response.set_cookie(
        key="forge_refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_HOURS * 3600,
        path="/auth",
    )
    response.set_cookie(
        key="forge_csrf_token",
        value=new_csrf_token,
        httponly=False,
        secure=not settings.DEBUG,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_HOURS * 3600,
        path="/",
    )

    event_broker.log_audit(
        event_type="auth_refresh",
        actor_ip=client_ip,
        details="Refreshed and rotated session token",
        status="success",
    )

    return AuthResponse(
        access_token=access_token,
        csrf_token=new_csrf_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout")
async def logout(request: Request, response: Response):
    refresh_cookie = request.cookies.get("forge_refresh_token")
    if refresh_cookie:
        try:
            payload = verify_refresh_token(refresh_cookie)
            jti = payload.get("jti")
            if jti:
                revoke_token(jti)
        except Exception:
            pass

    response.delete_cookie(key="forge_refresh_token", path="/auth")
    response.delete_cookie(key="forge_csrf_token", path="/")

    return {"message": "Logged out successfully."}
