"""JWT authentication: user registration, login, and a route dependency.

Users live in a small SQLite table (username + bcrypt hash). Login issues a
short-lived HS256 JWT; protected routes depend on `get_current_user`, which
verifies the token and returns the username (or raises 401).
"""
import sqlite3
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import config
from models import Token, UserCredentials

router = APIRouter(tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


# --- User store (SQLite) ---------------------------------------------------

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.AUTH_DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "username TEXT PRIMARY KEY, password_hash TEXT NOT NULL)"
    )
    return conn


def _create_user(username: str, password: str) -> None:
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, pw_hash),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Username already taken.")
    finally:
        conn.close()


def _verify_user(username: str, password: str) -> bool:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return False
    return bcrypt.checkpw(password.encode(), row[0].encode())


# --- JWT -------------------------------------------------------------------

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


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Route dependency: verify the Bearer token, return the username, or 401."""
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
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token.")
    return username


# --- Routes ----------------------------------------------------------------
# Defined as sync `def` so FastAPI runs them in a threadpool — bcrypt and
# sqlite are blocking and would otherwise stall the event loop.

@router.post("/register", response_model=Token)
def register(creds: UserCredentials) -> Token:
    if len(creds.username) < 3 or len(creds.password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Username must be ≥3 chars and password ≥8 chars.",
        )
    _create_user(creds.username, creds.password)
    return _issue_token(creds.username)


@router.post("/login", response_model=Token)
def login(creds: UserCredentials) -> Token:
    if not _verify_user(creds.username, creds.password):
        raise HTTPException(status_code=401, detail="Incorrect username or password.")
    return _issue_token(creds.username)
