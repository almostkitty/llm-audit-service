"""Проверка работоспособности сервиса и подключения к БД."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db.session import check_connection, get_session

router = APIRouter(tags=["health"])


@router.get("/api/health")
def api_health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/health/db")
def api_health_db(session: Annotated[Session, Depends(get_session)]) -> dict[str, str]:
    check_connection(session)
    return {"status": "ok", "database": "connected"}
