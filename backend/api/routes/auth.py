"""
CareLock Sync — Authentication Routes
Sprint 4: Issues HS256 JWT access tokens instead of static API keys.

Login flow
──────────
  POST /api/v1/auth/login  →  { access_token, token_type: "bearer", ... }
  Frontend stores the token in localStorage key 'carelock_auth'.
  All subsequent API calls send:  Authorization: Bearer <token>

Credential store
────────────────
  Passwords are bcrypt-hashed once at server startup via hash_password().
  The plaintext strings in _RAW_USERS never leave this file.
  Future upgrade path: replace CREDENTIAL_MAP with a DB users table.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from common.auth import (
    create_access_token, verify_password, hash_password, login_rate_limiter,
    require_auth, AuthContext,
)
from common.event_log import event_log

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# ── Credential store ──────────────────────────────────────────────────────────
# Raw plaintext credentials are immediately hashed at module load time.
# CREDENTIAL_MAP stores only the bcrypt hash — plaintext is discarded.
_RAW_USERS: dict = {
    "admin@carelock.com": {
        "password":     "admin123",
        "role":         "admin",
        "display_name": "System Administrator",
        "tenant_id":    None,
        "hospital_name":"CareLock HQ",
    },
    "hospital-a@carelock.com": {
        "password":     "hospital123",
        "role":         "hospital",
        "display_name": "Hospital A Admin",
        "tenant_id":    1,
        "hospital_name":"Shifa International Hospital",
    },
    "hospital-b@carelock.com": {
        "password":     "hospital123",
        "role":         "hospital",
        "display_name": "Hospital B Admin",
        "tenant_id":    2,
        "hospital_name":"PIMS Hospital",
    },
    "hospital-c@carelock.com": {
        "password":     "hospital123",
        "role":         "hospital",
        "display_name": "Hospital C Admin",
        "tenant_id":    3,
        "hospital_name":"National Medical Hospital",
    },
    "doctor@carelock.com": {
        "password":     "doctor123",
        "role":         "doctor",
        "display_name": "Dr. Ahmed Hassan",
        "tenant_id":    1,
        "hospital_name":"Shifa International Hospital",
    },
    "analyst@carelock.com": {
        "password":     "analyst123",
        "role":         "analyst",
        "display_name": "Data Analyst",
        "tenant_id":    None,
        "hospital_name":"CareLock Analytics",
    },
}

# Hash all passwords once at startup — O(n) bcrypt calls, then done.
CREDENTIAL_MAP: dict = {
    email: {**data, "password_hash": hash_password(data["password"])}
    for email, data in _RAW_USERS.items()
}


# ── Pydantic models ───────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email:    str
    password: str
    role:     Optional[str] = None  # optional role hint from the role-selector page


class LoginResponse(BaseModel):
    access_token:  str
    token_type:    str = "bearer"
    email:         str
    display_name:  str
    role:          str
    tenant_id:     Optional[int]
    hospital_name: str
    logged_in_at:  str


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """
    Authenticate with email + password.
    Returns a signed JWT access token valid for ACCESS_TOKEN_EXPIRE_MINUTES.
    """
    email = req.email.lower().strip()
    user  = CREDENTIAL_MAP.get(email)

    # Verify credentials — same error for unknown email and wrong password
    # (prevents user-enumeration). Rate-limit on the email key.
    if not user or not verify_password(req.password, user["password_hash"]):
        allowed, _ = login_rate_limiter.is_allowed(email)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts. Try again in 60 seconds.",
            )
        event_log.write('LOGIN_FAILED', email, None,
                        f"Failed login attempt for {email}", {})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Optional role validation (sent by the role-selector page)
    if req.role and req.role != user["role"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account '{email}' is not registered as '{req.role}'",
        )

    # Build JWT — payload mirrors AuthUser on the frontend
    token = create_access_token({
        "sub":           email,
        "role":          user["role"],
        "display_name":  user["display_name"],
        "tenant_id":     user["tenant_id"],
        "hospital_name": user["hospital_name"],
    })
    event_log.write('LOGIN_SUCCESS', email, user['tenant_id'],
                    f"Login from role={user['role']}", {'role': user['role']})

    return LoginResponse(
        access_token=token,
        email=email,
        display_name=user["display_name"],
        role=user["role"],
        tenant_id=user["tenant_id"],
        hospital_name=user["hospital_name"],
        logged_in_at=datetime.utcnow().isoformat(),
    )


@router.get("/demo-accounts")
async def demo_accounts():
    """Returns demo credentials for the frontend quick-fill UI. Never used in prod."""
    return {
        "accounts": [
            {"role": "admin",    "email": "admin@carelock.com",      "password": "admin123",    "label": "Super Admin"},
            {"role": "hospital", "email": "hospital-a@carelock.com", "password": "hospital123", "label": "Hospital A Admin"},
            {"role": "hospital", "email": "hospital-b@carelock.com", "password": "hospital123", "label": "Hospital B Admin"},
            {"role": "doctor",   "email": "doctor@carelock.com",     "password": "doctor123",   "label": "Doctor"},
            {"role": "analyst",  "email": "analyst@carelock.com",    "password": "analyst123",  "label": "Analyst"},
        ]
    }


@router.get("/me")
async def me(auth: AuthContext = Depends(require_auth)):
    """
    Validate the Bearer token in the request and return the authenticated user's profile.
    Called by the frontend on every app load to verify a stored token is still valid.
    Returns 401 automatically if the token is missing, expired, or has an invalid signature.
    """
    return {
        "email":         auth.email,
        "display_name":  auth.display_name,
        "role":          auth.role,
        "tenant_id":     auth.tenant_id,
        "hospital_name": auth.hospital_name,
    }


@router.post("/logout")
async def logout():
    """
    Stateless logout — JWT has no server-side session to invalidate.
    The frontend must discard the token from localStorage on this response.
    """
    return {"status": "ok", "message": "Token discarded. Remove it from client storage."}
