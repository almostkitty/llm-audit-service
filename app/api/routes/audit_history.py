"""История проверок /audit."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_session
from app.services.audit_history import audit_check_to_dict, list_audit_checks

router = APIRouter(prefix="/api/audit-history", tags=["audit-history"])


@router.get("")
def get_audit_history(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> dict:
    assert user.id is not None
    rows = list_audit_checks(session, user_id=user.id, limit=limit)
    items = [audit_check_to_dict(r) for r in rows]
    return {"items": items, "total": len(items)}
