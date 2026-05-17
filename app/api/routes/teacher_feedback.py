"""Оценки преподавателя по проверкам."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.api.deps import get_current_teacher
from app.db.models import User
from app.db.session import get_session
from app.schemas.teacher_feedback import TeacherFeedbackSubmit
from app.services.audit_history import get_audit_check_for_user
from app.services.teacher_feedback import (
    feedback_to_dict,
    get_teacher_feedback,
    list_teacher_feedback,
    save_teacher_feedback,
)

router = APIRouter(prefix="/api/teacher-feedback", tags=["teacher-feedback"])


@router.post("")
def submit_teacher_feedback(
    body: TeacherFeedbackSubmit,
    session: Annotated[Session, Depends(get_session)],
    teacher: Annotated[User, Depends(get_current_teacher)],
) -> dict:
    check = get_audit_check_for_user(session, body.audit_check_id, teacher)
    if check is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Проверка не найдена или недоступна",
        )
    try:
        row = save_teacher_feedback(
            session,
            teacher=teacher,
            audit_check_id=body.audit_check_id,
            agrees=body.agrees,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Проверка не найдена",
        ) from None
    return feedback_to_dict(row)


@router.get("/{audit_check_id}")
def get_feedback_for_check(
    audit_check_id: str,
    session: Annotated[Session, Depends(get_session)],
    teacher: Annotated[User, Depends(get_current_teacher)],
) -> dict:
    assert teacher.id is not None
    check = get_audit_check_for_user(session, audit_check_id, teacher)
    if check is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Проверка не найдена",
        )
    row = get_teacher_feedback(
        session,
        audit_check_id=audit_check_id,
        teacher_id=teacher.id,
    )
    if row is None:
        return {"feedback": None}
    return {"feedback": feedback_to_dict(row)}


@router.get("")
def list_my_feedback(
    session: Annotated[Session, Depends(get_session)],
    teacher: Annotated[User, Depends(get_current_teacher)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> dict:
    assert teacher.id is not None
    rows = list_teacher_feedback(session, teacher_id=teacher.id, limit=limit)
    items = [feedback_to_dict(r) for r in rows]
    return {"items": items, "total": len(items)}
