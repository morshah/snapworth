"""Cookie-based JWT authentication.

Login/register set the JWT in an **httpOnly** cookie, so the token is never
exposed to JavaScript (XSS can't read it). Protected routes depend on
`get_current_user`, which reads the cookie (falling back to an `Authorization:
Bearer` header so Swagger/API clients still work), verifies it, and returns the
User (or 401).
"""
import asyncio
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import config
from db import Invitation, User, get_session
from models import InviteInfo, InviteRegister, UserCredentials, UserOut
from ratelimit import limiter

router = APIRouter(tags=["auth"])


def _utcnow() -> datetime:
    """Naive UTC now, to compare against naive DB timestamps."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --- Password hashing (bcrypt is CPU-blocking → run off the event loop) -----

async def _hash_password(password: str) -> str:
    digest = await asyncio.to_thread(bcrypt.hashpw, password.encode(), bcrypt.gensalt())
    return digest.decode()


async def _check_password(password: str, password_hash: str) -> bool:
    return await asyncio.to_thread(
        bcrypt.checkpw, password.encode(), password_hash.encode()
    )


# --- JWT + cookie -----------------------------------------------------------

def _secret() -> str:
    if not config.JWT_SECRET:
        raise HTTPException(
            status_code=503,
            detail="JWT_SECRET is not configured. Set it in backend/.env to enable auth.",
        )
    return config.JWT_SECRET


def _encode_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=config.JWT_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": username, "exp": expire}, _secret(), algorithm=config.JWT_ALGORITHM
    )


def _set_auth_cookie(response: Response, username: str) -> None:
    response.set_cookie(
        key=config.COOKIE_NAME,
        value=_encode_token(username),
        httponly=True,
        secure=config.COOKIE_SECURE,
        samesite=config.COOKIE_SAMESITE,
        max_age=config.JWT_EXPIRE_MINUTES * 60,
        path="/",
    )


def _token_from_request(request: Request) -> str | None:
    """Prefer the httpOnly cookie; fall back to a Bearer header (Swagger/clients)."""
    token = request.cookies.get(config.COOKIE_NAME)
    if token:
        return token
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:]
    return None


async def get_current_user(
    request: Request, session: AsyncSession = Depends(get_session)
) -> User:
    """Route dependency: verify the auth cookie and load the user, or 401."""
    token = _token_from_request(request)
    if token is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    try:
        payload = jwt.decode(token, _secret(), algorithms=[config.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session.")

    user = await session.scalar(select(User).where(User.username == payload.get("sub")))
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid session.")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Route dependency: 403 unless the current user is an admin."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user


# --- Routes -----------------------------------------------------------------

@router.post("/register", response_model=UserOut)
@limiter.limit(config.LOGIN_RATE_LIMIT)
async def register(
    request: Request,
    response: Response,
    creds: InviteRegister,
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    """Invite-only registration: a valid, unused, unexpired token is required."""
    if len(creds.username) < 3 or len(creds.password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Username must be ≥3 chars and password ≥8 chars.",
        )

    invite = await session.scalar(
        select(Invitation).where(Invitation.token == creds.token)
    )
    if invite is None or invite.accepted_at is not None or invite.expires_at <= _utcnow():
        raise HTTPException(
            status_code=400, detail="This invitation is invalid or has expired."
        )

    user = User(
        username=creds.username,
        password_hash=await _hash_password(creds.password),
        is_admin=invite.grants_admin,
    )
    session.add(user)
    try:
        await session.flush()  # surface a duplicate username before consuming the invite
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Username already taken.")

    invite.accepted_at = _utcnow()  # single-use
    await session.commit()

    _set_auth_cookie(response, creds.username)
    return UserOut(username=creds.username, is_admin=user.is_admin)


@router.get("/invite/{token}", response_model=InviteInfo)
async def check_invite(
    token: str, session: AsyncSession = Depends(get_session)
) -> InviteInfo:
    """Public: lets the accept page verify an invite before showing the form."""
    invite = await session.scalar(select(Invitation).where(Invitation.token == token))
    valid = (
        invite is not None
        and invite.accepted_at is None
        and invite.expires_at > _utcnow()
    )
    return InviteInfo(valid=valid, email=invite.email if valid else None)


@router.post("/login", response_model=UserOut)
@limiter.limit(config.LOGIN_RATE_LIMIT)
async def login(
    request: Request,
    response: Response,
    creds: UserCredentials,
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    user = await session.scalar(select(User).where(User.username == creds.username))
    if user is None or not await _check_password(creds.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password.")
    _set_auth_cookie(response, creds.username)
    return UserOut(username=user.username, is_admin=user.is_admin)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    """Return the current user — used by the frontend to bootstrap auth state."""
    return UserOut(username=user.username, is_admin=user.is_admin)


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie(config.COOKIE_NAME, path="/")
    return {"detail": "Logged out."}
