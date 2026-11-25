import re
from datetime import datetime, timedelta
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_validator, model_validator

from app.config import settings
from app.models.user import Role

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,50}$")


class StrictModel(BaseModel):
    # Лишние поля (role, is_active, id...) — 422: защита от Mass Assignment (OWASP API3:2023)
    model_config = ConfigDict(extra="forbid")


def check_username(value: str) -> str:
    if not USERNAME_RE.match(value):
        raise ValueError("Логин: 3–50 латинских букв, цифр, точек, дефисов и подчёркиваний")
    return value


def check_password(password: str, username: str = "") -> str:
    if len(password.encode()) > 72:
        raise ValueError("Пароль длиннее 72 байт")
    if not (re.search(r"[A-Za-zА-Яа-яЁё]", password) and re.search(r"\d", password)):
        raise ValueError("Пароль должен содержать буквы и цифры")
    if username and username.lower() in password.lower():
        raise ValueError("Пароль не должен содержать логин")
    return password


class UserRegister(StrictModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)

    _username = field_validator("username")(classmethod(lambda cls, v: check_username(v)))

    @model_validator(mode="after")
    def _password_policy(self):
        check_password(self.password, self.username)
        return self


class RegisterResult(BaseModel):
    id: int
    username: str
    email: str
    requires_age_verification: bool
    # Токен для шагов регистрации до входа (возрастная верификация), 30 минут
    registration_token: Optional[str] = None


class LoginResult(BaseModel):
    """Ответ /auth/token. Токены — в httpOnly cookies; access_token в теле оставлен только
    для Swagger и API-клиентов без cookies (браузерный фронтенд его не сохраняет)."""

    model_config = ConfigDict(populate_by_name=True)

    twofa_required: bool = Field(False, serialization_alias="2fa_required")
    temp_token: Optional[str] = None
    access_token: Optional[str] = None
    token_type: str = "bearer"


class TwoFactorVerify(StrictModel):
    temp_token: str = Field(..., min_length=10, max_length=2048)
    code: str = Field(..., pattern=r"^\d{6}$")


class RefreshRequest(StrictModel):
    refresh_token: Optional[str] = Field(None, min_length=10, max_length=2048)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: Optional[str]
    role: Role
    is_active: bool
    created_at: datetime


class UserMe(UserOut):
    display_name: Optional[str] = None
    totp_enabled: bool = False
    is_email_verified: bool = False
    is_age_verified: bool = False
    age_verification_required: bool = False
    username_changed_at: Optional[datetime] = None
    avatar_key: Optional[str] = Field(None, exclude=True)

    @computed_field
    @property
    def avatar_url(self) -> Optional[str]:
        return f"/users/{self.id}/avatar?v={self.avatar_key.rsplit('/', 1)[-1][:8]}" if self.avatar_key else None

    @computed_field
    @property
    def next_username_change_at(self) -> Optional[datetime]:
        if not self.username_changed_at:
            return None
        return self.username_changed_at + timedelta(days=settings.username_change_cooldown_days)


class UserAdminUpdate(StrictModel):
    role: Optional[Role] = None
    is_active: Optional[bool] = None


class ProfileUpdate(StrictModel):
    display_name: Optional[str] = Field(None, max_length=50)


class UsernameChange(StrictModel):
    username: str = Field(..., min_length=3, max_length=50)
    _username = field_validator("username")(classmethod(lambda cls, v: check_username(v)))


class PasswordChange(StrictModel):
    current_password: str = Field(..., min_length=1, max_length=72)
    new_password: str = Field(..., min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def _policy(cls, value: str) -> str:
        return check_password(value)


class TotpCode(StrictModel):
    code: str = Field(..., pattern=r"^\d{6}$")


class TotpDisable(StrictModel):
    password: str = Field(..., min_length=1, max_length=72)
    code: str = Field(..., pattern=r"^\d{6}$")


class EmailRequest(StrictModel):
    email: EmailStr


class SessionOut(BaseModel):
    id: str
    created_at: datetime
    last_used_at: datetime
    user_agent: Optional[str]
    ip: Optional[str]
    current: bool
