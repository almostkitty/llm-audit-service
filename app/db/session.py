"""Подключение к БД, создание таблиц, зависимость FastAPI ``get_session``."""

from __future__ import annotations

from collections.abc import Generator

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import DATABASE_URL, PROJECT_ROOT, sql_echo

# Регистрация моделей в metadata
from app.db.models import AppSetting, AuditCheck, TeacherAuditFeedback, User  # noqa: F401

_engine_kwargs: dict = {"echo": sql_echo()}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_kwargs)


def _sqlite_table_exists(conn, table: str) -> bool:
    row = conn.execute(
        text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:t LIMIT 1"),
        {"t": table},
    ).first()
    return row is not None


def _sqlite_add_column_if_missing(conn, table: str, column: str, col_type: str) -> None:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    names = {row[1] for row in rows}
    if column not in names:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
        conn.commit()


def _sqlite_column_is_nullable(conn, table: str, column: str) -> bool | None:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    for row in rows:
        if row[1] == column:
            return row[3] == 0
    return None


def _sqlite_rebuild_users_names_not_null(conn) -> None:
    """Пересоздать users с NOT NULL для имён (SQLite не всегда умеет ALTER COLUMN)."""
    conn.execute(
        text(
            """
            CREATE TABLE users__names_nn (
                id INTEGER NOT NULL PRIMARY KEY,
                email VARCHAR(320) NOT NULL,
                first_name VARCHAR(100) NOT NULL,
                last_name VARCHAR(100) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                is_active BOOLEAN NOT NULL,
                role VARCHAR(32) NOT NULL,
                created_at DATETIME NOT NULL
            )
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO users__names_nn (
                id, email, first_name, last_name, password_hash, is_active, role, created_at
            )
            SELECT
                id,
                email,
                COALESCE(TRIM(first_name), ''),
                COALESCE(TRIM(last_name), ''),
                password_hash,
                is_active,
                role,
                created_at
            FROM users
            """
        )
    )
    conn.execute(text("DROP TABLE users"))
    conn.execute(text("ALTER TABLE users__names_nn RENAME TO users"))
    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_role ON users (role)"))
    conn.commit()


def _migrate_users_names_not_null(conn) -> None:
    """Заполнить NULL и выставить NOT NULL для first_name / last_name."""
    if not _sqlite_table_exists(conn, "users"):
        return
    _sqlite_add_column_if_missing(conn, "users", "first_name", "VARCHAR(100) NOT NULL DEFAULT ''")
    _sqlite_add_column_if_missing(conn, "users", "last_name", "VARCHAR(100) NOT NULL DEFAULT ''")
    conn.execute(text("UPDATE users SET first_name = '' WHERE first_name IS NULL"))
    conn.execute(text("UPDATE users SET last_name = '' WHERE last_name IS NULL"))
    conn.commit()
    needs_rebuild = any(
        _sqlite_column_is_nullable(conn, "users", col) for col in ("first_name", "last_name")
    )
    if needs_rebuild:
        _sqlite_rebuild_users_names_not_null(conn)


def _migrate_sqlite_columns() -> None:
    """Добавить новые колонки в существующие SQLite-таблицы (create_all их не меняет)."""
    if not DATABASE_URL.startswith("sqlite"):
        return
    with engine.connect() as conn:
        if _sqlite_table_exists(conn, "audit_checks"):
            _sqlite_add_column_if_missing(conn, "audit_checks", "report_json", "TEXT")
            _sqlite_add_column_if_missing(conn, "audit_checks", "user_id", "INTEGER")
        if _sqlite_table_exists(conn, "users"):
            _migrate_users_names_not_null(conn)


def init_db() -> None:
    """Создать каталог для файла SQLite при необходимости и применить схему (create_all)."""
    parsed = make_url(DATABASE_URL)
    if parsed.drivername == "sqlite" and parsed.database:
        db_path = Path(parsed.database)
        if not db_path.is_absolute():
            db_path = PROJECT_ROOT / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)
    _migrate_sqlite_columns()


def get_session() -> Generator[Session, None, None]:
    """Зависимость маршрутов: одна сессия на запрос."""
    with Session(engine) as session:
        yield session


def check_connection(session: Session) -> None:
    """Проверка работы БД (для health)."""
    session.execute(text("SELECT 1"))
