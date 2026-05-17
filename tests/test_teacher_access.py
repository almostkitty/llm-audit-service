"""Unit-тесты прав доступа к проверкам."""

from __future__ import annotations

from app.db.models import AuditCheck, User
from app.services.teacher_feedback import user_can_view_check


def _user(uid: int, role: str) -> User:
    return User(
        id=uid,
        email=f"{role}@test.com",
        first_name="A",
        last_name="B",
        password_hash="x",
        role=role,
    )


def _check(check_id: str, owner_id: int) -> AuditCheck:
    return AuditCheck(id=check_id, user_id=owner_id, filename="a.txt")


def test_owner_can_view_own_check():
    student = _user(1, "student")
    check = _check("c1", owner_id=1)
    assert user_can_view_check(student, check) is True


def test_teacher_can_view_foreign_check():
    teacher = _user(2, "teacher")
    check = _check("c1", owner_id=1)
    assert user_can_view_check(teacher, check) is True


def test_student_cannot_view_foreign_check():
    other = _user(2, "student")
    check = _check("c1", owner_id=1)
    assert user_can_view_check(other, check) is False


def test_missing_user_id_denied():
    teacher = _user(2, "teacher")
    teacher.id = None
    check = _check("c1", owner_id=1)
    assert user_can_view_check(teacher, check) is False
