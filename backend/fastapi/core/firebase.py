from __future__ import annotations

import json
from typing import Any, Dict

import firebase_admin
from fastapi import HTTPException, status
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials

from ..models.auth import FirebaseUser
from .config import settings

firebase_app = None


def _build_credentials() -> credentials.Certificate:
    if settings.firebase_credentials_json:
        try:
            payload: Dict[str, Any] = json.loads(settings.firebase_credentials_json)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive branch
            raise RuntimeError("FIREBASE_CREDENTIALS_JSON is not valid JSON") from exc
        return credentials.Certificate(payload)

    if settings.firebase_credentials_path:
        return credentials.Certificate(settings.firebase_credentials_path)

    raise RuntimeError("Firebase credentials are not configured. Set FIREBASE_CREDENTIALS_JSON or FIREBASE_CREDENTIALS_PATH.")


def _ensure_firebase_app() -> firebase_admin.App:
    global firebase_app
    if firebase_app:
        return firebase_app

    cred = _build_credentials()
    firebase_app = firebase_admin.initialize_app(
        credential=cred,
        options={"projectId": settings.firebase_project_id} if settings.firebase_project_id else None,
    )
    return firebase_app


def verify_id_token(token: str) -> FirebaseUser:
    try:
        _ensure_firebase_app()
        decoded = firebase_auth.verify_id_token(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Firebase ID token.",
        ) from exc

    uid = decoded.get("uid")
    if not uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Firebase token missing user id.")

    return FirebaseUser(
        user_id=uid,
        email=decoded.get("email"),
        name=decoded.get("name"),
        picture=decoded.get("picture"),
    )


