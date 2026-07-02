"""JWT authentication: user registration, login, and a route dependency.

Users are persisted via SQLAlchemy (see db.py). Login issues a short-lived
HS256 JWT; protected routes depend on `get_current_user`, which verifies the
token, loads the user, and returns the ORM object (or raises 401).
"""
import asyncio
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import config
from db import User, get_session
from models import Token, UserCredentials

router = APIRouter(tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


# --- Password hashing (bcrypt is CPU-blocking → run off the event loop) -----

async def _hash_password(password: str) -> str:
    digest = await asyncio.to_thread(bcrypt.hashpw, password.encode(), bcrypt.gensalt())
    return digest.decode()


async def _check_password(password: str, password_hash: str) -> bool:
    return await asyncio.to_thread(
        bcrypt.checkpw, password.encode(), password_hash.encode()
    )


# --- JWT --------------------------------------------------------------------

def _secret() -> str:
    if not config.JWT_SECRET:
        raise HTTPException(
            status_code=503,
            detail="JWT_SECRET is not configured. Set it in backend/.env to enable auth.",
        )
    return config.JWT_SECRET


def _issue_token(username: str) -> Token:
    expire = datetime.now(timezone.utc) + timedelta(minutes=config.JWT_EXPIRE_MINUTES)
    payload = {"sub": username, "exp": expire}
    encoded = jwt.encode(payload, _secret(), algorithm=config.JWT_ALGORITHM)
    return Token(access_token=encoded)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Route dependency: verify the Bearer token and load the user, or 401."""
    if creds is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    try:
        payload = jwt.decode(
            creds.credentials, _secret(), algorithms=[config.JWT_ALGORITHM]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")

    username = payload.get("sub")
    user = await session.scalar(select(User).where(User.username == username))
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token.")
    return user


# --- Routes -----------------------------------------------------------------

@router.post("/register", response_model=Token)
async def register(
    creds: UserCredentials, session: AsyncSession = Depends(get_session)
) -> Token:
    if len(creds.username) < 3 or len(creds.password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Username must be ≥3 chars and password ≥8 chars.",
        )
    user = User(
        username=creds.username, password_hash=await _hash_password(creds.password)
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Username already taken.")
    return _issue_token(creds.username)


@router.post("/login", response_model=Token)
async def login(
    creds: UserCredentials, session: AsyncSession = Depends(get_session)
) -> Token:
    user = await session.scalar(select(User).where(User.username == creds.username))
    if user is None or not await _check_password(creds.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password.")
    return _issue_token(creds.username)
