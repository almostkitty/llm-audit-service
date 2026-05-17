"""100% покрытие CRUD пользователя: POST register/login, GET/PATCH/DELETE /api/auth/me."""

from __future__ import annotations

from sqlmodel import select

from app.db.models import AuditCheck, TeacherAuditFeedback, User
from app.services.audit_history import record_audit_check


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _minimal_audit() -> dict:
    return {
        "metrics": {"lexical_diversity": 0.5},
        "llm_probability": 0.2,
        "scoring": {},
        "hidden_unicode": {"has_signals": False},
    }


def test_register_duplicate_email(client, register_user):
    register_user("dup@example.com")
    res = client.post(
        "/api/auth/register",
        json={
            "email": "dup@example.com",
            "password": "secret12",
            "password_confirm": "secret12",
            "role": "student",
            "first_name": "A",
            "last_name": "B",
        },
    )
    assert res.status_code == 400
    assert "зарегистрирован" in res.json()["detail"].lower()


def test_me_requires_auth(client):
    assert client.get("/api/auth/me").status_code == 401


def test_login_inactive_account(client, register_user, session):
    register_user("inactive@example.com")
    user = session.exec(select(User).where(User.email == "inactive@example.com")).first()
    assert user is not None
    user.is_active = False
    session.add(user)
    session.commit()

    res = client.post(
        "/api/auth/login",
        json={"email": "inactive@example.com", "password": "secret12"},
    )
    assert res.status_code == 403
    assert "отключён" in res.json()["detail"].lower()


def test_patch_names_without_password(client, register_user):
    token = register_user("patch@example.com", first_name="Старое", last_name="Имя")
    res = client.patch(
        "/api/auth/me",
        headers=_auth(token),
        json={"first_name": "Новое", "last_name": "Фамилия"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["first_name"] == "Новое"
    assert data["last_name"] == "Фамилия"

    me = client.get("/api/auth/me", headers=_auth(token))
    assert me.json()["first_name"] == "Новое"


def test_patch_empty_body(client, register_user):
    token = register_user("empty@example.com")
    res = client.patch("/api/auth/me", headers=_auth(token), json={})
    assert res.status_code == 400
    assert "обновления" in res.json()["detail"].lower()


def test_patch_email_success(client, register_user):
    token = register_user("oldmail@example.com")
    res = client.patch(
        "/api/auth/me",
        headers=_auth(token),
        json={
            "email": "newmail@example.com",
            "current_password": "secret12",
        },
    )
    assert res.status_code == 200
    assert res.json()["email"] == "newmail@example.com"

    login = client.post(
        "/api/auth/login",
        json={"email": "newmail@example.com", "password": "secret12"},
    )
    assert login.status_code == 200


def test_patch_email_wrong_password(client, register_user):
    token = register_user("wp@example.com")
    res = client.patch(
        "/api/auth/me",
        headers=_auth(token),
        json={"email": "other@example.com", "current_password": "bad"},
    )
    assert res.status_code == 401


def test_patch_email_already_taken(client, register_user):
    register_user("owner@example.com")
    token = register_user("grab@example.com")
    res = client.patch(
        "/api/auth/me",
        headers=_auth(token),
        json={"email": "owner@example.com", "current_password": "secret12"},
    )
    assert res.status_code == 400
    assert "занят" in res.json()["detail"].lower()


def test_patch_password_success(client, register_user):
    token = register_user("pwd@example.com")
    res = client.patch(
        "/api/auth/me",
        headers=_auth(token),
        json={
            "current_password": "secret12",
            "new_password": "newsecret99",
        },
    )
    assert res.status_code == 200

    old = client.post(
        "/api/auth/login",
        json={"email": "pwd@example.com", "password": "secret12"},
    )
    assert old.status_code == 401

    new = client.post(
        "/api/auth/login",
        json={"email": "pwd@example.com", "password": "newsecret99"},
    )
    assert new.status_code == 200


def test_patch_password_wrong_current(client, register_user):
    token = register_user("pwd2@example.com")
    res = client.patch(
        "/api/auth/me",
        headers=_auth(token),
        json={"current_password": "nope", "new_password": "newsecret99"},
    )
    assert res.status_code == 401


def test_delete_account_success(client, register_user, session):
    token = register_user("del@example.com", role="teacher")
    user = session.exec(select(User).where(User.email == "del@example.com")).first()
    assert user and user.id is not None

    record_audit_check(
        session,
        user_id=user.id,
        filename="x.txt",
        text="текст",
        audit_result=_minimal_audit(),
    )

    res = client.request(
        "DELETE",
        "/api/auth/me",
        headers=_auth(token),
        json={"password": "secret12"},
    )
    assert res.status_code == 204

    assert session.get(User, user.id) is None
    checks = session.exec(select(AuditCheck).where(AuditCheck.user_id == user.id)).all()
    assert checks == []

    me = client.get("/api/auth/me", headers=_auth(token))
    assert me.status_code == 401


def test_delete_account_wrong_password(client, register_user):
    token = register_user("del2@example.com")
    res = client.request(
        "DELETE",
        "/api/auth/me",
        headers=_auth(token),
        json={"password": "wrong"},
    )
    assert res.status_code == 401

    me = client.get("/api/auth/me", headers=_auth(token))
    assert me.status_code == 200


def test_delete_teacher_removes_feedback(client, register_user, session):
    student_token = register_user("stud@example.com")
    teacher_token = register_user("teach@example.com", role="teacher")
    check_id = client.post(
        "/audit",
        headers=_auth(student_token),
        files={"file": ("a.txt", "Текст проверки.".encode(), "text/plain")},
    ).json()["check_id"]

    client.post(
        "/api/teacher-feedback",
        headers=_auth(teacher_token),
        json={"audit_check_id": check_id, "agrees": True},
    )
    teacher = session.exec(select(User).where(User.email == "teach@example.com")).first()
    assert teacher and teacher.id is not None
    fb_before = session.exec(
        select(TeacherAuditFeedback).where(TeacherAuditFeedback.teacher_id == teacher.id)
    ).all()
    assert len(fb_before) == 1

    client.request(
        "DELETE",
        "/api/auth/me",
        headers=_auth(teacher_token),
        json={"password": "secret12"},
    )

    fb_after = session.exec(
        select(TeacherAuditFeedback).where(TeacherAuditFeedback.teacher_id == teacher.id)
    ).all()
    assert fb_after == []
