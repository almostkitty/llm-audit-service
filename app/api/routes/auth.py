"""Регистрация, вход, профиль (JWT)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import User
from app.db.session import get_session
from app.services.audit_history import delete_checks_for_user
from app.services.teacher_feedback import delete_feedback_for_teacher
from app.schemas.auth import (
    DeleteAccountRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserLogin,
    UserPublic,
    UserRegister,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(body: UserRegister, session: Annotated[Session, Depends(get_session)]) -> TokenResponse:
    existing = session.exec(select(User).where(User.email == body.email)).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email уже зарегистрирован")

    user = User(
        email=body.email.lower().strip(),
        first_name=body.first_name,
        last_name=body.last_name,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    assert user.id is not None
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(body: UserLogin, session: Annotated[Session, Depends(get_session)]) -> TokenResponse:
    user = session.exec(select(User).where(User.email == body.email.lower().strip())).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Аккаунт отключён")
    assert user.id is not None
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserPublic)
def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user


@router.patch("/me", response_model=UserPublic)
def update_me(
    body: UpdateProfileRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> User:
    if body.email is not None or body.new_password is not None:
        if not body.current_password or not verify_password(body.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный текущий пароль",
            )
    updates = body.model_dump(exclude_unset=True)
    updates.pop("current_password", None)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нет данных для обновления",
        )
    if "first_name" in updates:
        user.first_name = body.first_name
    if "last_name" in updates:
        user.last_name = body.last_name
    if body.email is not None:
        new_email = body.email.lower().strip()
        if new_email != user.email:
            taken = session.exec(select(User).where(User.email == new_email)).first()
            if taken is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Этот email уже занят",
                )
            user.email = new_email
    if body.new_password is not None:
        user.password_hash = hash_password(body.new_password)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(
    body: DeleteAccountRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный пароль",
        )
    assert user.id is not None
    delete_checks_for_user(session, user.id)
    delete_feedback_for_teacher(session, user.id)
    session.delete(user)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
