"""API отчётов проверки (только для авторизованного владельца)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_session
from app.services.audit_history import get_audit_check_for_user, list_audit_checks
from app.services.report_builder import enrich_report_for_display, report_from_json

router = APIRouter(prefix="/api/reports", tags=["reports"])
_last_reports: dict[int, dict[str, object]] = {}


def save_last_report(user_id: int, report: dict[str, object]) -> None:
    _last_reports[user_id] = report


def resolve_report(
    session: Session,
    report_id: str,
    user: User,
) -> dict[str, object]:
    assert user.id is not None
    uid = user.id

    if report_id == "last":
        cached = _last_reports.get(uid)
        if cached is not None:
            return enrich_report_for_display(dict(cached))
        rows = list_audit_checks(session, user_id=uid, limit=1)
        if rows and rows[0].report_json:
            parsed = report_from_json(rows[0].report_json)
            if parsed:
                return parsed
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Отчёт 'last' пока недоступен: сначала выполните проверку на главной странице",
        )

    row = get_audit_check_for_user(session, report_id, user)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Отчёт '{report_id}' не найден",
        )
    parsed = report_from_json(row.report_json)
    if parsed is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Для проверки '{report_id}' отчёт не сохранён (старая запись)",
        )
    return parsed


@router.get("")
def list_reports(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    assert user.id is not None
    rows = list_audit_checks(session, user_id=user.id, limit=20)
    items = [
        {
            "id": row.id,
            "title": row.filename,
            "checked_at": row.checked_at.isoformat(),
            "has_report": bool(row.report_json),
        }
        for row in rows
        if row.report_json
    ]
    return {"items": items, "total": len(items)}


@router.get("/{report_id}")
def get_report(
    report_id: str,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    return resolve_report(session, report_id, user)
