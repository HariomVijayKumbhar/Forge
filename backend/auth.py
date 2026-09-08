import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
import jwt
from fastapi import Depends, HTTPException, Security, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session, select

from passlib.context import CryptContext

from backend.config import settings
from backend.db import engine, RevokedToken, User

security_bearer = HTTPBearer(auto_error=False)
ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password_constant_time(provided_password: str) -> bool:
    return secrets.compare_digest(provided_password, settings.ACCESS_PASSWORD)


def create_access_token(subject: str = "admin") -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.ACCESS_TOKEN_SECRET, algorithm=ALGORITHM)


def create_refresh_token(subject: str = "admin") -> Tuple[str, str]:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=settings.REFRESH_TOKEN_EXPIRE_HOURS)
    jti = str(uuid.uuid4())
    payload = {
        "sub": subject,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": jti,
    }
    token = jwt.encode(payload, settings.REFRESH_TOKEN_SECRET, algorithm=ALGORITHM)
    return token, jti


def generate_csrf_token() -> str:
    return secrets.token_hex(32)


def is_token_revoked(jti: str) -> bool:
    with Session(engine) as session:
        statement = select(RevokedToken).where(RevokedToken.jti == jti)
        result = session.exec(statement).first()
        return result is not None


def revoke_token(jti: str):
    with Session(engine) as session:
        revoked = RevokedToken(jti=jti, revoked_at=datetime.now(timezone.utc))
        session.add(revoked)
        session.commit()


def verify_refresh_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.REFRESH_TOKEN_SECRET, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type.")
        jti = payload.get("jti")
        if not jti or is_token_revoked(jti):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked.")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    with Session(engine) as session:
        statement = select(User).where(User.username == username)
        user = session.exec(statement).first()
        if not user:
            statement = select(User).where(User.email == username)
            user = session.exec(statement).first()
        if user:
            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "is_active": user.is_active,
                "hashed_password": user.hashed_password,
            }
        return None


async def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer)) -> Dict[str, Any]:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.ACCESS_TOKEN_SECRET, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type.")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
