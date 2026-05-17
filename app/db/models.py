"""ORM-модели приложения (пользователи, настройки). SQLite сейчас; для PostgreSQL достаточно сменить DATABASE_URL."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    """Учётная запись для будущей авторизации."""

    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True, max_length=320)
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    password_hash: str = Field(max_length=255)
    is_active: bool = Field(default=True)
    role: str = Field(default="user", max_length=32, index=True)
    created_at: datetime = Field(default_factory=_utc_now)


class AppSetting(SQLModel, table=True):
    """Ключ–значение для глобальных настроек (лимиты, флаги)."""

    __tablename__ = "app_settings"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True, max_length=128)
    value: str = Field(default="")
    updated_at: datetime = Field(default_factory=_utc_now)


class AuditCheck(SQLModel, table=True):
    """Запись одной проверки через POST /audit."""

    __tablename__ = "audit_checks"

    id: str = Field(primary_key=True, max_length=36)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    filename: str = Field(max_length=255, index=True)
    checked_at: datetime = Field(default_factory=_utc_now, index=True)
    llm_probability: Optional[float] = Field(default=None)
    report_json: Optional[str] = Field(default=None)


class TeacherAuditFeedback(SQLModel, table=True):
    """Оценка преподавателя: согласен ли с результатом детекции по проверке."""

    __tablename__ = "teacher_audit_feedback"
    __table_args__ = ({"sqlite_autoincrement": True},)

    id: Optional[int] = Field(default=None, primary_key=True)
    audit_check_id: str = Field(foreign_key="audit_checks.id", max_length=36, index=True)
    teacher_id: int = Field(foreign_key="users.id", index=True)
    agrees_with_detection: bool = Field(index=True)
    filename: str = Field(max_length=255)
    llm_probability: Optional[float] = Field(default=None)
    metrics_json: str = Field(default="{}")
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
