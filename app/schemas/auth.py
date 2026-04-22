from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field

# Роли при самостоятельной регистрации
RegistrationRole = Literal["student", "teacher"]


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    role: RegistrationRole = "student"


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

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    """Смена email и/или пароля; всегда нужен текущий пароль."""

    current_password: str = Field(min_length=1, max_length=128)
    email: EmailStr | None = None
    new_password: str | None = Field(None, min_length=6, max_length=128)


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)
