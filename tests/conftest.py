"""Фикстуры для unit- и API-тестов веб-приложения."""

from __future__ import annotations

import os

# До импорта app: in-memory SQLite и тестовый JWT.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-32-characters-min!!")
os.environ.setdefault("ENABLE_CATBOOST", "0")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.api.routes import reports as reports_routes
from app.core.config import DATABASE_URL
from app.db import session as db_session
from app.db.models import AppSetting, AuditCheck, TeacherAuditFeedback, User  # noqa: F401
from app.db.session import get_session, init_db
from app.main import app

# Одна in-memory БД на все соединения (иначе таблицы «пропадают» между сессиями).
db_session.engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
engine = db_session.engine


@pytest.fixture(autouse=True)
def _fresh_db():
    SQLModel.metadata.drop_all(engine)
    init_db()
    reports_routes._last_reports.clear()
    yield
    reports_routes._last_reports.clear()


@pytest.fixture
def session() -> Session:
    with Session(engine) as s:
        yield s


@pytest.fixture
def client(session: Session) -> TestClient:
    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    def _make(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture
def register_user(client: TestClient):
    def _register(
        email: str,
        *,
        password: str = "secret12",
        role: str = "student",
        first_name: str = "Иван",
        last_name: str = "Тестов",
    ) -> str:
        res = client.post(
            "/api/auth/register",
            json={
                "email": email,
                "password": password,
                "password_confirm": password,
                "role": role,
                "first_name": first_name,
                "last_name": last_name,
            },
        )
        assert res.status_code == 200, res.text
        return res.json()["access_token"]

    return _register
