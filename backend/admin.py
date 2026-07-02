"""Admin-only endpoints: invitation management and user management.

Every route is gated by `require_admin` (403 for non-admins). "Adding a user"
means issuing an invite link (registration is invite-only); existing users can
be edited (role / password reset) or deleted.
"""
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

import config
from auth import _hash_password, _utcnow, require_admin
from db import Invitation, Report, User, get_session
from models import (
    InvitationCreate,
    InvitationOut,
    UserAdminOut,
    UserUpdate,
)

router = APIRouter(tags=["admin"], dependencies=[Depends(require_admin)])


def _invite_out(inv: Invitation) -> InvitationOut:
    return InvitationOut(
        id=inv.id,
        token=inv.token,
        email=inv.email,
        grants_admin=inv.grants_admin,
        created_at=inv.created_at,
        expires_at=inv.expires_at,
        accepted_at=inv.accepted_at,
    )


def _user_out(u: User) -> UserAdminOut:
    return UserAdminOut(
        id=u.id, username=u.username, is_admin=u.is_admin, created_at=u.created_at
    )


# --- Invitations -----------------------------------------------------------

@router.post("/invitations", response_model=InvitationOut)
async def create_invitation(
    payload: InvitationCreate,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> InvitationOut:
    invite = Invitation(
        token=secrets.token_urlsafe(32),
        email=payload.email,
        grants_admin=payload.grants_admin,
        created_by_id=admin.id,
        expires_at=_utcnow() + timedelta(days=config.INVITE_EXPIRE_DAYS),
    )
    session.add(invite)
    await session.commit()
    await session.refresh(invite)
    return _invite_out(invite)


@router.get("/invitations", response_model=list[InvitationOut])
async def list_invitations(
    session: AsyncSession = Depends(get_session),
) -> list[InvitationOut]:
    rows = await session.scalars(
        select(Invitation).order_by(Invitation.created_at.desc())
    )
    return [_invite_out(i) for i in rows]


@router.delete("/invitations/{invitation_id}")
async def delete_invitation(
    invitation_id: int, session: AsyncSession = Depends(get_session)
) -> dict:
    invite = await session.get(Invitation, invitation_id)
    if invite is None:
        raise HTTPException(status_code=404, detail="Invitation not found.")
    await session.delete(invite)
    await session.commit()
    return {"detail": "Invitation revoked."}


# --- Users -----------------------------------------------------------------

@router.get("/users", response_model=list[UserAdminOut])
async def list_users(
    session: AsyncSession = Depends(get_session),
) -> list[UserAdminOut]:
    rows = await session.scalars(select(User).order_by(User.created_at.asc()))
    return [_user_out(u) for u in rows]


@router.patch("/users/{user_id}", response_model=UserAdminOut)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> UserAdminOut:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    if payload.is_admin is not None:
        if user.id == admin.id and payload.is_admin is False:
            raise HTTPException(
                status_code=400, detail="You can't remove your own admin access."
            )
        user.is_admin = payload.is_admin

    if payload.password is not None:
        if len(payload.password) < 8:
            raise HTTPException(status_code=400, detail="Password must be ≥8 chars.")
        user.password_hash = await _hash_password(payload.password)

    await session.commit()
    return _user_out(user)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="You can't delete your own account.")

    # Reports FK-reference the user; remove them first.
    await session.execute(delete(Report).where(Report.user_id == user_id))
    await session.delete(user)
    await session.commit()
    return {"detail": "User deleted."}
