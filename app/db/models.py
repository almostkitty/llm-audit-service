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
    password_hash: str = Field(max_length=255)
    is_active: bool = Field(default=True)
    role: str = Field(default="user", max_length=32, index=True)
    created_at: datetime = Field(default_factory=_utc_now)


class AppSetting(SQLModel, table=True):
    """Ключ–значение для глобальных настроек (лимиты, флаги), редактируемых админом."""

    __tablename__ = "app_settings"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True, max_length=128)
    value: str = Field(default="")
    updated_at: datetime = Field(default_factory=_utc_now)
