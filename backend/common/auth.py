"""
CareLock Sync — JWT Authentication & Authorization
Sprint 4: API-key system replaced with HS256 JWT Bearer tokens.

JWT payload structure
─────────────────────
{
  "sub":           "admin@carelock.com",   ← standard claim (email)
  "role":          "admin",
  "display_name":  "System Administrator",
  "tenant_id":     null,
  "hospital_name": "CareLock HQ",
  "iat":           1712000000,
  "exp":           1712001800
}

Route usage
───────────
  from common.auth import get_current_user, require_role, AuthContext

  @router.get("/protected")
  async def ep(auth: AuthContext = Depends(get_current_user)):
      ...

  @router.post("/admin-only")
  async def ep(auth: AuthContext = Depends(require_role("admin"))):
      ...

  # Multi-role shorthand
  @router.post("/write-op")
  async def ep(auth: AuthContext = Depends(require_write)):
      ...
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import jwt, JWTError, ExpiredSignatureError
from typing import Optional
from datetime import datetime, timedelta
from collections import defaultdict, deque
import threading

from common.config import settings

# ── Password hashing (bcrypt via passlib) ────────────────────────────────────
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return bcrypt hash of a plaintext password."""
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time bcrypt verification."""
    return _pwd_ctx.verify(plain, hashed)


# ── JWT utility functions ────────────────────────────────────────────────────
_bearer = HTTPBearer(auto_error=True)


def create_access_token(data: dict) -> str:
    """
    Encode a signed HS256 JWT.
    Automatically injects 'iat' and 'exp' claims.
    """
    payload = data.copy()
    now = datetime.utcnow()
    payload.update({
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    })
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_access_token(token: str) -> dict:
    """
    Decode and fully verify a JWT (signature + expiry).
    Raises HTTP 401 on any failure so callers never need to handle jose exceptions.

    Error responses:
      - Expired token  → 401  "Token expired. Please log in again."
      - Bad signature  → 401  "Token signature is invalid."
      - Any other flaw → 401  "Token is invalid."
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("sub") is None:
            raise JWTError("Missing 'sub' claim")
        return payload
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── AuthContext — returned to every protected endpoint ───────────────────────
class AuthContext(BaseModel):
    email:         str
    display_name:  str
    role:          str           # admin | hospital | doctor | analyst
    tenant_id:     Optional[int] = None
    hospital_name: Optional[str] = None

    def can_access_tenant(self, tid: int) -> bool:
        """Admins see all tenants; other roles are scoped to their own tenant."""
        if self.role == "admin":
            return True
        return self.tenant_id == tid

    def assert_tenant(self, tid: int) -> None:
        """Raise 403 if this user cannot access the requested tenant."""
        if not self.can_access_tenant(tid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access denied: your account is scoped to tenant {self.tenant_id}, "
                    f"cannot access tenant {tid}"
                ),
            )


# ── Sliding-window rate limiter ──────────────────────────────────────────────
class RateLimiter:
    """Thread-safe sliding-window rate limiter (used on the login endpoint)."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window = timedelta(seconds=window_seconds)
        self._buckets: dict = defaultdict(deque)
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> tuple[bool, int]:
        """Returns (allowed, remaining). Trims stale entries each call."""
        now = datetime.utcnow()
        cutoff = now - self.window
        with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                return False, 0
            bucket.append(now)
            return True, self.max_requests - len(bucket)


# 10 failed login attempts per minute per email (brute-force protection)
login_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)


# ── Core FastAPI dependency ───────────────────────────────────────────────────
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> AuthContext:
    """
    Primary auth dependency.
    Validates the Bearer token and returns a populated AuthContext.
    Used directly on any route that needs the full user object.
    """
    payload = verify_access_token(credentials.credentials)
    return AuthContext(
        email=payload["sub"],
        display_name=payload.get("display_name", payload["sub"]),
        role=payload["role"],
        tenant_id=payload.get("tenant_id"),
        hospital_name=payload.get("hospital_name"),
    )


# ── Role-guard factory ────────────────────────────────────────────────────────
def require_role(*roles: str):
    """
    Dependency factory that wraps get_current_user with a role check.

    Usage:
        auth: AuthContext = Depends(require_role("admin"))
        auth: AuthContext = Depends(require_role("admin", "hospital"))
    """
    async def _check(auth: AuthContext = Depends(get_current_user)) -> AuthContext:
        if auth.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{auth.role}' is not authorised. Required one of: {list(roles)}",
            )
        return auth
    return _check


# ── Convenience aliases ───────────────────────────────────────────────────────
# Existing route files (patients.py, sync.py, rag.py) import these names.
# No changes required in those files.
require_auth  = get_current_user          # any authenticated user
require_admin = require_role("admin")     # admin only
require_write = require_role("admin", "hospital")  # admin or hospital
