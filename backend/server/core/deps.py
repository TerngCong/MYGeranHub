from fastapi import Header, HTTPException, status

from ..models.auth import FirebaseUser
from .firebase import verify_id_token


def _extract_bearer_token(auth_header: str | None) -> str:
    if not auth_header:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header.")

    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header must be in the format: Bearer <token>.")

    return token.strip()


def get_current_user(authorization: str | None = Header(default=None)) -> FirebaseUser:
    token = _extract_bearer_token(authorization)
    return verify_id_token(token)



