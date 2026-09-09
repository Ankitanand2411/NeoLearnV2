import base64

import jwt
import structlog
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from jwt.jwks_client import PyJWKClient

from app.core.config import settings

security = HTTPBearer()
log = structlog.get_logger()

# JWKS client to verify asymmetric tokens (ES256/RS256) dynamically from Supabase
jwks_url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
jwks_client = PyJWKClient(jwks_url)


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    """
    Validates the Supabase JWT using PyJWT.
    Supports both HS256 (symmetric) and ES256/RS256 (asymmetric via JWKS).
    Raises 401 if token is invalid or expired.
    """
    token = credentials.credentials

    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")
    except Exception as e_hdr:
        log.error("jwt_header_extract_failed", error=str(e_hdr))
        alg = "HS256"

    # 1. Asymmetric signature verification (e.g. ES256 or RS256)
    if alg in ["ES256", "RS256"]:
        try:
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                options={"verify_aud": False},
            )
            return payload
        except Exception as e_jwks:
            log.error("jwt_jwks_verification_failed", alg=alg, error=str(e_jwks))
            raise HTTPException(
                status_code=401,
                detail=f"Invalid or expired token. JWKS signature verification failed: {str(e_jwks)}"
            ) from e_jwks

    # 2. Symmetric signature verification (HS256 using JWT Secret)
    secret = settings.SUPABASE_JWT_SECRET

    try:
        # Try raw secret string
        return jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except InvalidTokenError as e_raw:
        try:
            # Fallback to base64 decoded secret bytes
            padded_secret = secret
            missing_padding = len(padded_secret) % 4
            if missing_padding:
                padded_secret += '=' * (4 - missing_padding)
            decoded_secret = base64.b64decode(padded_secret)
            return jwt.decode(
                token,
                decoded_secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
        except Exception as e_b64:
            log.error("jwt_hs256_verification_failed", raw_error=str(e_raw), b64_error=str(e_b64))
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token. Signature verification failed."
            ) from e_b64


def get_current_user(payload: dict = Depends(verify_token)) -> dict:
    """Extracts user info from the validated JWT payload."""
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing user subject")
    return {"id": user_id, "email": payload.get("email", "")}
