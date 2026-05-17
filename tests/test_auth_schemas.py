"""Unit-тесты схем регистрации и профиля."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.auth import UpdateProfileRequest, UserRegister


def test_user_register_passwords_must_match():
    with pytest.raises(ValidationError) as exc:
        UserRegister(
            email="a@example.com",
            password="secret12",
            password_confirm="other12",
            first_name="Иван",
            last_name="Иванов",
        )
    assert "Пароли не совпадают" in str(exc.value)


def test_user_register_strips_names():
    user = UserRegister(
        email="a@example.com",
        password="secret12",
        password_confirm="secret12",
        first_name="  Иван ",
        last_name=" Петров ",
    )
    assert user.first_name == "Иван"
    assert user.last_name == "Петров"


def test_user_register_rejects_empty_name():
    with pytest.raises(ValidationError):
        UserRegister(
            email="a@example.com",
            password="secret12",
            password_confirm="secret12",
            first_name="   ",
            last_name="Иванов",
        )


def test_update_profile_requires_password_for_email_change():
    with pytest.raises(ValidationError) as exc:
        UpdateProfileRequest(email="new@example.com")
    assert "текущий пароль" in str(exc.value).lower()


def test_update_profile_allows_name_change_without_password():
    body = UpdateProfileRequest(first_name="Новое")
    assert body.first_name == "Новое"
    assert body.current_password is None
