"""ORM-модели приложения (SQLite; для PostgreSQL — сменить DATABASE_URL)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    """Учётная запись (студент или преподаватель)."""

    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=320)
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    password_hash: str = Field(max_length=255)
    is_active: bool = Field(default=True)
    role: str = Field(default="student", max_length=32, index=True)
    created_at: datetime = Field(default_factory=_utc_now)


class AppSetting(SQLModel, table=True):
    """Глобальные настройки сервиса (ключ–значение), зарезервировано под админ-конфиг."""

    __tablename__ = "app_settings"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True, max_length=128)
    value: str = Field(default="")
    updated_at: datetime = Field(default_factory=_utc_now)


class AuditCheck(SQLModel, table=True):
    """Одна проверка текста пользователя (результат POST /audit)."""

    __tablename__ = "audit_checks"

    id: str = Field(primary_key=True, max_length=36)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    filename: str = Field(max_length=255, index=True)
    checked_at: datetime = Field(default_factory=_utc_now, index=True)
    llm_probability: Optional[float] = Field(default=None, index=True)
    report_json: Optional[str] = Field(default=None, description="Полный отчёт для UI (JSON)")


class TeacherAuditFeedback(SQLModel, table=True):
    """Оценка преподавателя по проверке (одна запись на пару проверка + преподаватель)."""

    __tablename__ = "teacher_audit_feedback"
    __table_args__ = (
        UniqueConstraint("audit_check_id", "teacher_id", name="uq_teacher_feedback_check_teacher"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    audit_check_id: str = Field(
        foreign_key="audit_checks.id",
        max_length=36,
        index=True,
        ondelete="CASCADE",
    )
    teacher_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    agrees_with_detection: bool
    filename: str = Field(max_length=255, description="Снимок имени файла на момент оценки")
    llm_probability: Optional[float] = Field(
        default=None,
        description="Снимок P(LLM) на момент оценки",
    )
    metrics_json: str = Field(
        default="{}",
        description="Снимок метрик на момент оценки (JSON)",
    )
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
