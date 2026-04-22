"""Настройки приложения. Путь к SQLite по умолчанию: ``data/app.db`` в корне проекта."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Путь к файлу SQLite по умолчанию (каталог ``data/`` в .gitignore)
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "data" / "app.db"


def get_database_url() -> str:
    url = (os.getenv("DATABASE_URL") or "").strip()
    if url:
        return url
    return f"sqlite:///{DEFAULT_SQLITE_PATH}"


def sql_echo() -> bool:
    return os.getenv("SQL_ECHO", "").strip().lower() in ("1", "true", "yes")


DATABASE_URL = get_database_url()

# JWT (в продакшене задайте свой длинный секрет в окружении)
JWT_SECRET = (os.getenv("JWT_SECRET") or "dev-secret-min-32-chars-long!!").strip()
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int((os.getenv("JWT_EXPIRE_MINUTES") or "4320").strip() or "4320")  # 3 дня по умолчанию
