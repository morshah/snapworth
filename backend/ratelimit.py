"""Rate limiting (slowapi).

Login/register are limited per client IP (brute-force protection); uploads are
limited per authenticated user (cost protection — each upload spends money).

Storage defaults to in-memory (per-process). For a multi-instance deployment,
set RATE_LIMIT_STORAGE_URI to a shared backend, e.g. redis://host:6379.
"""
import jwt
from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

import config


def user_or_ip(request: Request) -> str:
    """Key by the JWT subject when authenticated, else by client IP.

    Lets us cap uploads per user rather than per IP (several users behind one
    NAT shouldn't share a bucket).
    """
    token = request.cookies.get(config.COOKIE_NAME)
    if not token:
        header = request.headers.get("authorization", "")
        if header.lower().startswith("bearer "):
            token = header[7:]
    if token and config.JWT_SECRET:
        try:
            payload = jwt.decode(
                token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM]
            )
            sub = payload.get("sub")
            if sub:
                return f"user:{sub}"
        except jwt.InvalidTokenError:
            pass
    return get_remote_address(request)


limiter = Limiter(
    key_func=get_remote_address,  # default: per-IP
    storage_uri=config.RATE_LIMIT_STORAGE_URI,  # None → in-memory
)


def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return a clean, frontend-friendly 429 (matches our `detail` convention)."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please slow down and try again shortly."},
    )
