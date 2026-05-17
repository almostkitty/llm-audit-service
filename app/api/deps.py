"""Зависимости FastAPI: текущий пользователь по Bearer JWT или cookie."""

from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from app.core.security import decode_access_token
from app.db.models import User
from app.db.session import get_session

_bearer = HTTPBearer(auto_error=False)


def _token_from_request(
    creds: HTTPAuthorizationCredentials | None,
    access_token: str | None,
) -> str | None:
    if creds is not None and creds.scheme.lower() == "bearer" and creds.credentials:
        return creds.credentials
    if access_token:
        return access_token.strip()
    return None


def _user_from_token(session: Session, token: str) -> User | None:
    try:
        payload = decode_access_token(token)
        uid = int(payload["sub"])
    except Exception:
        return None
    user = session.get(User, uid)
    if user is None or not user.is_active:
        return None
    return user


def get_optional_user(
    session: Annotated[Session, Depends(get_session)],
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    access_token: Annotated[str | None, Cookie(alias="access_token")] = None,
) -> User | None:
    token = _token_from_request(creds, access_token)
    if not token:
        return None
    return _user_from_token(session, token)


def get_current_user(
    user: Annotated[User | None, Depends(get_optional_user)],
) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_teacher(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if user.role != "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступно только для роли «преподаватель»",
        )
    return user
