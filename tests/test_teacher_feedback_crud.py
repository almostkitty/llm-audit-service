"""CRUD оценок преподавателя: Create/Update POST, Read GET, Delete — каскадом с аккаунтом."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlmodel import select

from app.db.models import TeacherAuditFeedback, User
from app.services.teacher_feedback import (
    _metrics_from_report,
    delete_feedback_for_checks,
    feedback_to_dict,
    get_audit_check_if_allowed,
    get_teacher_feedback,
    save_teacher_feedback,
)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _student_check(client, student_token: str) -> str:
    res = client.post(
        "/audit",
        headers=_auth(student_token),
        files={"file": ("t.txt", "Текст для оценки преподавателя.".encode(), "text/plain")},
    )
    assert res.status_code == 200
    return res.json()["check_id"]


def test_feedback_create_read_update(client, register_user):
    student_token = register_user("fb_stu@example.com")
    teacher_token = register_user("fb_tch@example.com", role="teacher")
    check_id = _student_check(client, student_token)

    missing = client.get(
        f"/api/teacher-feedback/{check_id}",
        headers=_auth(teacher_token),
    )
    assert missing.status_code == 200
    assert missing.json()["feedback"] is None

    created = client.post(
        "/api/teacher-feedback",
        headers=_auth(teacher_token),
        json={"audit_check_id": check_id, "agrees": True},
    )
    assert created.status_code == 200
    assert created.json()["agrees_with_detection"] is True

    updated = client.post(
        "/api/teacher-feedback",
        headers=_auth(teacher_token),
        json={"audit_check_id": check_id, "agrees": False},
    )
    assert updated.status_code == 200
    assert updated.json()["agrees_with_detection"] is False

    read = client.get(
        f"/api/teacher-feedback/{check_id}",
        headers=_auth(teacher_token),
    )
    assert read.json()["feedback"]["agrees_with_detection"] is False


def test_feedback_list(client, register_user):
    student_token = register_user("fb2_stu@example.com")
    teacher_token = register_user("fb2_tch@example.com", role="teacher")
    check_id = _student_check(client, student_token)

    client.post(
        "/api/teacher-feedback",
        headers=_auth(teacher_token),
        json={"audit_check_id": check_id, "agrees": True},
    )

    listed = client.get("/api/teacher-feedback?limit=10", headers=_auth(teacher_token))
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert body["items"][0]["audit_check_id"] == check_id


def test_feedback_check_not_found(client, register_user):
    teacher_token = register_user("fb3_tch@example.com", role="teacher")

    post = client.post(
        "/api/teacher-feedback",
        headers=_auth(teacher_token),
        json={"audit_check_id": "00000000-0000-0000-0000-000000000088", "agrees": True},
    )
    assert post.status_code == 404

    get = client.get(
        "/api/teacher-feedback/00000000-0000-0000-0000-000000000088",
        headers=_auth(teacher_token),
    )
    assert get.status_code == 404


def test_feedback_service_helpers(session, register_user, client):
    student_token = register_user("fb4_stu@example.com")
    teacher_token = register_user("fb4_tch@example.com", role="teacher")
    check_id = _student_check(client, student_token)

    client.post(
        "/api/teacher-feedback",
        headers=_auth(teacher_token),
        json={"audit_check_id": check_id, "agrees": True},
    )

    teacher = session.exec(select(User).where(User.email == "fb4_tch@example.com")).first()
    assert teacher and teacher.id is not None

    row = get_teacher_feedback(session, audit_check_id=check_id, teacher_id=teacher.id)
    assert row is not None
    d = feedback_to_dict(row)
    assert d["audit_check_id"] == check_id
    assert "metrics" in d

    delete_feedback_for_checks(session, [])
    delete_feedback_for_checks(session, [check_id])
    session.commit()
    assert (
        get_teacher_feedback(session, audit_check_id=check_id, teacher_id=teacher.id) is None
    )


def test_get_audit_check_if_allowed_denied(session, register_user, client):
    student_token = register_user("fb5_stu@example.com")
    register_user("fb5_other@example.com", role="student")
    check_id = _student_check(client, student_token)

    other_user = session.exec(select(User).where(User.email == "fb5_other@example.com")).first()
    assert other_user
    assert get_audit_check_if_allowed(session, check_id, other_user) is None
    assert get_audit_check_if_allowed(session, "missing-id", other_user) is None


def test_metrics_from_report_skips_invalid_rows():
    metrics = _metrics_from_report(
        {
            "metrics": [
                "bad",
                {"key": "burstiness", "value": 4.0},
                {"key": "x", "value": "n/a"},
            ]
        }
    )
    assert metrics == {"burstiness": 4.0}


def test_save_teacher_feedback_raises_when_check_missing(session, register_user):
    teacher = User(
        id=99,
        email="orphan@example.com",
        first_name="T",
        last_name="T",
        password_hash="x",
        role="teacher",
    )
    with pytest.raises(ValueError, match="check_not_found"):
        save_teacher_feedback(
            session,
            teacher=teacher,
            audit_check_id="00000000-0000-0000-0000-000000000077",
            agrees=True,
        )


def test_feedback_route_maps_value_error(client, register_user):
    student_token = register_user("fb6_stu@example.com")
    teacher_token = register_user("fb6_tch@example.com", role="teacher")
    check_id = _student_check(client, student_token)

    with patch(
        "app.api.routes.teacher_feedback.save_teacher_feedback",
        side_effect=ValueError("check_not_found"),
    ):
        res = client.post(
            "/api/teacher-feedback",
            headers=_auth(teacher_token),
            json={"audit_check_id": check_id, "agrees": True},
        )
    assert res.status_code == 404
    assert "не найдена" in res.json()["detail"].lower()


def test_feedback_to_dict_invalid_metrics_json():
    row = TeacherAuditFeedback(
        id=1,
        audit_check_id="c1",
        teacher_id=1,
        agrees_with_detection=True,
        filename="f.txt",
        metrics_json="{not-json",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    data = feedback_to_dict(row)
    assert data["metrics"] == {}
