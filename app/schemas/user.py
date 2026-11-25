import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.user import Role

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,50}$")


class StrictModel(BaseModel):
    # Лишние поля (role, is_active, id...) — 422, а не молчаливое игнорирование:
    # защита от Mass Assignment (OWASP API3:2023)
    model_config = ConfigDict(extra="forbid")


class UserRegister(StrictModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    password: str = Field(..., min_length=8, max_length=72)

    @field_validator("username")
    @classmethod
    def _username(cls, value: str) -> str:
        if not USERNAME_RE.match(value):
            raise ValueError("Логин: латинские буквы, цифры, точка, дефис и подчёркивание")
        return value

    @model_validator(mode="after")
    def _password_policy(self):
        password = self.password
        if len(password.encode()) > 72:
            raise ValueError("Пароль длиннее 72 байт")
        if not (re.search(r"[A-Za-zА-Яа-яЁё]", password) and re.search(r"\d", password)):
            raise ValueError("Пароль должен содержать буквы и цифры")
        if self.username.lower() in password.lower():
            raise ValueError("Пароль не должен содержать логин")
        return self


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(StrictModel):
    refresh_token: str = Field(..., min_length=10, max_length=2048)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: Optional[str]
    role: Role
    is_active: bool
    created_at: datetime


class UserAdminUpdate(StrictModel):
    role: Optional[Role] = None
    is_active: Optional[bool] = None
