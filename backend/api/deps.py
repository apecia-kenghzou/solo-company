"""Shared FastAPI dependencies."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from models.base import AsyncSessionLocal
from models.user import User
from sqlalchemy import select


async def get_db() -> AsyncSession:
    """Yield an async SQLAlchemy session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user(
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: AsyncSession = None,
) -> User:
    """Stub auth dependency — reads user ID from ``X-User-Id`` header.

    In production this will be replaced by Clerk JWT verification.
    For now it looks up the user by ID from the header.

    Raises:
        HTTPException 401: if header is missing.
        HTTPException 404: if user is not found in DB.
    """
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-Id header is required",
        )

    # Import here to avoid circular imports
    from models.base import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        try:
            uid = UUID(x_user_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-User-Id must be a valid UUID",
            )

        user = await session.execute(select(User).where(User.id == uid))
        user = user.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {x_user_id} not found",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )
        return user
