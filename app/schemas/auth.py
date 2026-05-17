from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

# Роли при самостоятельной регистрации
RegistrationRole = Literal["student", "teacher"]


def _require_name(value: str | None) -> str:
    if value is None:
        raise ValueError("Имя и фамилия обязательны")
    stripped = str(value).strip()
    if not stripped:
        raise ValueError("Имя и фамилия не могут быть пустыми")
    return stripped


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    password_confirm: str = Field(min_length=6, max_length=128)
    role: RegistrationRole = "student"
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def normalize_names(cls, value: str | None) -> str:
        return _require_name(value)

    @model_validator(mode="after")
    def passwords_match(self) -> UserRegister:
        if self.password != self.password_confirm:
            raise ValueError("Пароли не совпадают")
        return self


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserPublic(BaseModel):
    id: int
    email: str
    role: str
    first_name: str
    last_name: str

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    """Смена профиля; пароль нужен только для смены email или пароля."""

    current_password: str | None = Field(None, min_length=1, max_length=128)
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    email: EmailStr | None = None
    new_password: str | None = Field(None, min_length=6, max_length=128)

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def normalize_names(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_name(value)

    @model_validator(mode="after")
    def password_required_for_sensitive(self) -> UpdateProfileRequest:
        if (self.email is not None or self.new_password is not None) and not self.current_password:
            raise ValueError("Для смены email или пароля укажите текущий пароль")
        return self


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)
