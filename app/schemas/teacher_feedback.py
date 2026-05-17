from __future__ import annotations

from pydantic import BaseModel, Field


class TeacherFeedbackSubmit(BaseModel):
    audit_check_id: str = Field(..., min_length=1, max_length=36)
    agrees: bool = Field(..., description="Согласен ли преподаватель с результатом детекции")
