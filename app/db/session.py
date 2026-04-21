"""Подключение к БД, создание таблиц, зависимость FastAPI ``get_session``."""

from __future__ import annotations

from collections.abc import Generator

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import DATABASE_URL, PROJECT_ROOT, sql_echo

# Регистрация моделей в metadata
from app.db.models import AppSetting, User  # noqa: F401

_engine_kwargs: dict = {"echo": sql_echo()}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_kwargs)


def init_db() -> None:
    """Создать каталог для файла SQLite при необходимости и применить схему (create_all)."""
    parsed = make_url(DATABASE_URL)
    if parsed.drivername == "sqlite" and parsed.database:
        db_path = Path(parsed.database)
        if not db_path.is_absolute():
            db_path = PROJECT_ROOT / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Зависимость маршрутов: одна сессия на запрос."""
    with Session(engine) as session:
        yield session


def check_connection(session: Session) -> None:
    """Проверка работы БД (для health)."""
    session.execute(text("SELECT 1"))
