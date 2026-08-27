"""
API Authentication Dependencies — Sprint 4
Re-exports the JWT dependency functions from common.auth.

Any route file that imports from here will continue to work after
the migration from API keys to JWT Bearer tokens.

Direct import (preferred for new routes):
    from common.auth import get_current_user, require_role, AuthContext

Legacy import (existing route files — no changes required):
    from api.dependencies import get_current_user, require_auth, require_admin
"""

from common.auth import (      # noqa: F401  (re-exports)
    AuthContext,
    get_current_user,
    require_role,
    require_auth,
    require_admin,
    require_write,
)

# Alias for routes that annotate the injected user as CurrentUser
CurrentUser = AuthContext

__all__ = [
    "AuthContext",
    "CurrentUser",
    "get_current_user",
    "require_role",
    "require_auth",
    "require_admin",
    "require_write",
]
