"""
Tests for app.core.security.verify_token / get_current_user.

Covers all three verification paths without any network:
  * HS256 with the secret used as a raw string
  * HS256 with the secret base64-decoded to bytes (Supabase's legacy format)
  * ES256 via JWKS, with the JWKS client monkeypatched to return a local key
"""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core import security
from tests.conftest import HS256_RAW_KEY, HS256_SECRET_SETTING


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _claims(**overrides) -> dict:
    now = int(time.time())
    claims = {"sub": "user-123", "email": "s@example.com", "iat": now, "exp": now + 300, "aud": "authenticated"}
    claims.update(overrides)
    return claims


# ─── HS256 ────────────────────────────────────────────────────────────────────

def test_hs256_with_raw_secret_string():
    token = jwt.encode(_claims(), HS256_SECRET_SETTING, algorithm="HS256")
    payload = security.verify_token(_creds(token))
    assert payload["sub"] == "user-123"


def test_hs256_with_base64_decoded_secret_bytes():
    # Signed with the decoded bytes: the raw-string attempt must fail and the
    # base64 fallback must succeed.
    token = jwt.encode(_claims(), HS256_RAW_KEY, algorithm="HS256")
    payload = security.verify_token(_creds(token))
    assert payload["sub"] == "user-123"


def test_expired_token_is_rejected():
    token = jwt.encode(_claims(exp=int(time.time()) - 10), HS256_SECRET_SETTING, algorithm="HS256")
    with pytest.raises(HTTPException) as exc:
        security.verify_token(_creds(token))
    assert exc.value.status_code == 401


def test_wrong_secret_is_rejected():
    token = jwt.encode(_claims(), "some-other-secret", algorithm="HS256")
    with pytest.raises(HTTPException) as exc:
        security.verify_token(_creds(token))
    assert exc.value.status_code == 401


def test_garbage_token_is_rejected():
    with pytest.raises(HTTPException) as exc:
        security.verify_token(_creds("not.a.jwt"))
    assert exc.value.status_code == 401


# ─── ES256 via JWKS ───────────────────────────────────────────────────────────

def test_es256_uses_jwks_signing_key(monkeypatch):
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()

    class _SigningKey:
        key = public_key

    monkeypatch.setattr(security.jwks_client, "get_signing_key_from_jwt", lambda token: _SigningKey())

    token = jwt.encode(_claims(), private_key, algorithm="ES256", headers={"kid": "test-kid"})
    payload = security.verify_token(_creds(token))
    assert payload["sub"] == "user-123"


def test_es256_with_wrong_key_is_rejected(monkeypatch):
    signer = ec.generate_private_key(ec.SECP256R1())
    other = ec.generate_private_key(ec.SECP256R1()).public_key()

    class _SigningKey:
        key = other

    monkeypatch.setattr(security.jwks_client, "get_signing_key_from_jwt", lambda token: _SigningKey())

    token = jwt.encode(_claims(), signer, algorithm="ES256")
    with pytest.raises(HTTPException) as exc:
        security.verify_token(_creds(token))
    assert exc.value.status_code == 401


# ─── get_current_user ─────────────────────────────────────────────────────────

def test_get_current_user_extracts_id_and_email():
    user = security.get_current_user({"sub": "u1", "email": "a@b.c"})
    assert user == {"id": "u1", "email": "a@b.c"}


def test_get_current_user_requires_sub():
    with pytest.raises(HTTPException) as exc:
        security.get_current_user({"email": "a@b.c"})
    assert exc.value.status_code == 401
