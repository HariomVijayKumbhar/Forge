import pytest
import time
from backend.auth import (
    create_access_token,
    create_refresh_token,
    verify_token,
    verify_refresh_token,
    revoke_token,
    is_token_revoked,
    generate_csrf_token,
)
from backend.db import init_db
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def test_access_token_creation_and_validation():
    token = create_access_token("admin_test")
    assert isinstance(token, str)

    # Validate token
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    import asyncio
    payload = asyncio.run(verify_token(creds))
    assert payload["sub"] == "admin_test"
    assert payload["type"] == "access"


def test_invalid_access_token():
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid.token.here")
    import asyncio
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(verify_token(creds))
    assert exc_info.value.status_code == 401


def test_refresh_token_rotation_and_revocation():
    token, jti = create_refresh_token("admin_test")
    assert not is_token_revoked(jti)

    payload = verify_refresh_token(token)
    assert payload["jti"] == jti

    # Revoke token
    revoke_token(jti)
    assert is_token_revoked(jti)

    # Verification should fail now
    with pytest.raises(HTTPException) as exc_info:
        verify_refresh_token(token)
    assert exc_info.value.status_code == 401
    assert "revoked" in str(exc_info.value.detail).lower()


def test_csrf_token_generation():
    token1 = generate_csrf_token()
    token2 = generate_csrf_token()
    assert len(token1) == 64
    assert token1 != token2
