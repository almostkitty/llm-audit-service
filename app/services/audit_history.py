"""Сохранение и чтение истории проверок /audit (по пользователю)."""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.db.models import AuditCheck, User
from app.services.report_builder import build_audit_report, report_from_json
from app.services.teacher_feedback import delete_feedback_for_checks, user_can_view_check


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_filename(name: str | None) -> str:
    raw = (name or "").strip()
    if not raw:
        return "input.txt"
    base = raw.replace("\\", "/").split("/")[-1]
    if len(base) > 255:
        base = base[:252] + "..."
    return base or "input.txt"


def record_audit_check(
    session: Session,
    *,
    user_id: int,
    filename: str | None,
    text: str,
    audit_result: dict[str, Any],
    char_count_before: int | None = None,
) -> tuple[AuditCheck, dict[str, Any]]:
    p = audit_result.get("llm_probability")
    llm_probability: float | None
    if isinstance(p, (int, float)) and not math.isnan(float(p)):
        llm_probability = float(p)
    else:
        llm_probability = None

    check_id = str(uuid.uuid4())
    checked_at = _utc_now()
    report = build_audit_report(
        audit_result,
        filename=filename,
        text=text,
        check_id=check_id,
        checked_at=checked_at,
        char_count_before=char_count_before,
    )

    row = AuditCheck(
        id=check_id,
        user_id=user_id,
        filename=_safe_filename(filename),
        checked_at=checked_at,
        llm_probability=llm_probability,
        report_json=json.dumps(report, ensure_ascii=False),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row, report


def get_audit_check_for_user(
    session: Session,
    check_id: str,
    user: User,
) -> AuditCheck | None:
    row = session.get(AuditCheck, check_id)
    if row is None:
        return None
    if not user_can_view_check(user, row):
        return None
    return row


def get_check_report_for_user(
    session: Session,
    check_id: str,
    user: User,
) -> dict[str, Any] | None:
    row = get_audit_check_for_user(session, check_id, user)
    if row is None:
        return None
    return report_from_json(row.report_json)


def list_audit_checks(
    session: Session,
    *,
    user_id: int,
    limit: int = 50,
) -> list[AuditCheck]:
    limit = max(1, min(limit, 500))
    stmt = (
        select(AuditCheck)
        .where(AuditCheck.user_id == user_id)
        .order_by(AuditCheck.checked_at.desc())
        .limit(limit)
    )
    return list(session.exec(stmt).all())


def delete_checks_for_user(session: Session, user_id: int) -> None:
    rows = session.exec(select(AuditCheck).where(AuditCheck.user_id == user_id)).all()
    check_ids = [r.id for r in rows]
    delete_feedback_for_checks(session, check_ids)
    for row in rows:
        session.delete(row)


def audit_check_to_dict(row: AuditCheck) -> dict[str, Any]:
    return {
        "id": row.id,
        "filename": row.filename,
        "checked_at": row.checked_at.isoformat(),
        "llm_probability": row.llm_probability,
        "has_report": bool(row.report_json),
    }
