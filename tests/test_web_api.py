"""API- и страничные тесты веб-приложения (FastAPI TestClient)."""

from __future__ import annotations

from sqlmodel import select

from app.api.routes import reports as reports_routes
from app.db.models import User
from app.services.audit_history import record_audit_check


def _minimal_audit() -> dict:
    return {
        "metrics": {"lexical_diversity": 0.5, "burstiness": 4.0, "unicode": 0.0},
        "llm_probability": 0.25,
        "scoring": {"mode": "unavailable"},
        "hidden_unicode": {"has_signals": False, "total_flagged_characters": 0},
    }


def _run_audit(client, token: str, text: str = "Тестовый текст для проверки."):
    return client.post(
        "/audit",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("sample.txt", text.encode("utf-8"), "text/plain")},
    )


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert "running" in res.json()["message"].lower()


def test_register_login_me(client, register_user):
    token = register_user("student@example.com", role="student")
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    data = me.json()
    assert data["email"] == "student@example.com"
    assert data["role"] == "student"
    assert data["first_name"] == "Иван"


def test_login_wrong_password(client, register_user):
    register_user("user@example.com")
    res = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "wrong-pass"},
    )
    assert res.status_code == 401


def test_audit_requires_auth(client):
    res = client.post(
        "/audit",
        files={"file": ("a.txt", b"hello", "text/plain")},
    )
    assert res.status_code == 401


def test_audit_and_history(client, register_user):
    token = register_user("auditor@example.com")
    audit_res = _run_audit(client, token)
    assert audit_res.status_code == 200
    body = audit_res.json()
    assert body.get("check_id")
    assert body.get("report_url", "").startswith("/report/")

    hist = client.get("/api/audit-history", headers={"Authorization": f"Bearer {token}"})
    assert hist.status_code == 200
    items = hist.json()["items"]
    assert len(items) == 1
    assert items[0]["has_report"] is True


def test_report_api_owner_and_teacher(client, register_user, session):
    student_token = register_user("stu@example.com", role="student")
    teacher_token = register_user("tch@example.com", role="teacher")

    audit_res = _run_audit(client, student_token)
    check_id = audit_res.json()["check_id"]

    owner_report = client.get(
        f"/api/reports/{check_id}",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert owner_report.status_code == 200
    assert owner_report.json()["id"] == check_id

    teacher_report = client.get(
        f"/api/reports/{check_id}",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert teacher_report.status_code == 200

    other_student = register_user("other@example.com", role="student")
    denied = client.get(
        f"/api/reports/{check_id}",
        headers={"Authorization": f"Bearer {other_student}"},
    )
    assert denied.status_code == 404


def test_teacher_feedback_submit_and_get(client, register_user):
    student_token = register_user("s1@example.com", role="student")
    teacher_token = register_user("t1@example.com", role="teacher")
    check_id = _run_audit(client, student_token).json()["check_id"]

    submit = client.post(
        "/api/teacher-feedback",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={"audit_check_id": check_id, "agrees": True},
    )
    assert submit.status_code == 200
    assert submit.json()["agrees_with_detection"] is True

    loaded = client.get(
        f"/api/teacher-feedback/{check_id}",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert loaded.status_code == 200
    assert loaded.json()["feedback"]["agrees_with_detection"] is True


def test_teacher_feedback_forbidden_for_student(client, register_user):
    student_token = register_user("s2@example.com", role="student")
    check_id = _run_audit(client, student_token).json()["check_id"]

    res = client.post(
        "/api/teacher-feedback",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"audit_check_id": check_id, "agrees": False},
    )
    assert res.status_code == 403


def test_html_pages_render(client):
    for path in ("/", "/info", "/login", "/register", "/history", "/account"):
        res = client.get(path)
        assert res.status_code == 200
        assert "LLM Audit" in res.text or "llm" in res.text.lower()


def test_report_page_requires_login(client, register_user):
    guest = client.get("/report/00000000-0000-0000-0000-000000000099")
    assert guest.status_code == 401
    assert "Войдите" in guest.text

    token = register_user("rep@example.com")
    check_id = _run_audit(client, token).json()["check_id"]
    page = client.get(f"/report/{check_id}", headers={"Authorization": f"Bearer {token}"})
    assert page.status_code == 200
    assert "Отчёт проверки текста" in page.text
    assert "Скопировать ссылку на отчёт" in page.text


def test_report_page_teacher_feedback_block(client, register_user):
    student_token = register_user("stu3@example.com", role="student")
    teacher_token = register_user("tch3@example.com", role="teacher")
    check_id = _run_audit(client, student_token).json()["check_id"]

    teacher_page = client.get(
        f"/report/{check_id}",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert teacher_page.status_code == 200
    assert "Оценка преподавателя" in teacher_page.text

    student_page = client.get(
        f"/report/{check_id}",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert "Оценка преподавателя" not in student_page.text


def test_resolve_report_last_from_db(client, register_user, session):
    token = register_user("last@example.com")
    user = session.exec(select(User).where(User.email == "last@example.com")).first()
    assert user and user.id is not None

    row, report = record_audit_check(
        session,
        user_id=user.id,
        filename="thesis.txt",
        text="Пример текста.",
        audit_result=_minimal_audit(),
    )
    reports_routes._last_reports.clear()

    api = client.get("/api/reports/last", headers={"Authorization": f"Bearer {token}"})
    assert api.status_code == 200
    assert api.json()["id"] == row.id


def test_thesis_clean_public(client):
    res = client.post("/thesis-clean", json={"text": "Введение\n\nТекст работы."})
    assert res.status_code == 200
    assert "text" in res.json()


def test_demo_redirect(client):
    res = client.get("/demo", follow_redirects=False)
    assert res.status_code == 307
    assert res.headers["location"] == "/"
