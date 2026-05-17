"""Оценки преподавателя по результатам проверки."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.db.models import AuditCheck, TeacherAuditFeedback, User
from app.services.report_builder import report_from_json


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def user_can_view_check(user: User, check: AuditCheck) -> bool:
    if user.id is None or check.user_id is None:
        return False
    if check.user_id == user.id:
        return True
    return user.role == "teacher"


def get_audit_check_if_allowed(
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


def _metrics_from_report(report: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in report.get("metrics") or []:
        if not isinstance(row, dict):
            continue
        key = row.get("key")
        val = row.get("value")
        if key and isinstance(val, (int, float)):
            out[str(key)] = float(val)
    return out


def save_teacher_feedback(
    session: Session,
    *,
    teacher: User,
    audit_check_id: str,
    agrees: bool,
) -> TeacherAuditFeedback:
    assert teacher.id is not None
    check = get_audit_check_if_allowed(session, audit_check_id, teacher)
    if check is None:
        raise ValueError("check_not_found")

    report = report_from_json(check.report_json) or {}
    llm_p = report.get("summary", {}).get("llm_probability")
    if llm_p is None:
        llm_p = check.llm_probability
    metrics = _metrics_from_report(report)

    existing = session.exec(
        select(TeacherAuditFeedback).where(
            TeacherAuditFeedback.audit_check_id == audit_check_id,
            TeacherAuditFeedback.teacher_id == teacher.id,
        )
    ).first()

    now = _utc_now()
    if existing is not None:
        existing.agrees_with_detection = agrees
        existing.filename = check.filename
        existing.llm_probability = float(llm_p) if llm_p is not None else None
        existing.metrics_json = json.dumps(metrics, ensure_ascii=False)
        existing.updated_at = now
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    row = TeacherAuditFeedback(
        audit_check_id=audit_check_id,
        teacher_id=teacher.id,
        agrees_with_detection=agrees,
        filename=check.filename,
        llm_probability=float(llm_p) if llm_p is not None else None,
        metrics_json=json.dumps(metrics, ensure_ascii=False),
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def get_teacher_feedback(
    session: Session,
    *,
    audit_check_id: str,
    teacher_id: int,
) -> TeacherAuditFeedback | None:
    return session.exec(
        select(TeacherAuditFeedback).where(
            TeacherAuditFeedback.audit_check_id == audit_check_id,
            TeacherAuditFeedback.teacher_id == teacher_id,
        )
    ).first()


def feedback_to_dict(row: TeacherAuditFeedback) -> dict[str, Any]:
    try:
        metrics = json.loads(row.metrics_json or "{}")
    except json.JSONDecodeError:
        metrics = {}
    return {
        "id": row.id,
        "audit_check_id": row.audit_check_id,
        "teacher_id": row.teacher_id,
        "agrees_with_detection": row.agrees_with_detection,
        "filename": row.filename,
        "llm_probability": row.llm_probability,
        "metrics": metrics,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def list_teacher_feedback(
    session: Session,
    *,
    teacher_id: int,
    limit: int = 100,
) -> list[TeacherAuditFeedback]:
    limit = max(1, min(limit, 500))
    stmt = (
        select(TeacherAuditFeedback)
        .where(TeacherAuditFeedback.teacher_id == teacher_id)
        .order_by(TeacherAuditFeedback.updated_at.desc())
        .limit(limit)
    )
    return list(session.exec(stmt).all())


def delete_feedback_for_teacher(session: Session, teacher_id: int) -> None:
    rows = session.exec(
        select(TeacherAuditFeedback).where(TeacherAuditFeedback.teacher_id == teacher_id)
    ).all()
    for row in rows:
        session.delete(row)


def delete_feedback_for_checks(session: Session, check_ids: list[str]) -> None:
    if not check_ids:
        return
    for cid in check_ids:
        rows = session.exec(
            select(TeacherAuditFeedback).where(TeacherAuditFeedback.audit_check_id == cid)
        ).all()
        for row in rows:
            session.delete(row)
