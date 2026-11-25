"""Управление пользователями — только для администратора."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.database import get_db
from app.models import Role, User
from app.schemas.user import UserAdminUpdate, UserOut

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_admin)])


@router.get("/", response_model=List[UserOut], summary="Список пользователей")
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).order_by(User.id).offset(skip).limit(limit))
    return result.scalars().all()


@router.patch("/{user_id}", response_model=UserOut, summary="Изменить роль или заблокировать")
async def update_user(
    body: UserAdminUpdate,
    user_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id and (body.role not in (None, Role.ADMIN) or body.is_active is False):
        raise HTTPException(status_code=400, detail="You cannot demote or block yourself")
    if body.role is not None:
        user.role = body.role.value
    if body.is_active is not None:
        user.is_active = body.is_active
    user.token_version += 1  # старые access-токены пользователя сразу перестают действовать
    await db.commit()
    return user
