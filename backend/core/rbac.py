"""Role-Based Access Control (RBAC) Module for VeriCred.

Enforces server-side role resolution and route authorization:
1. Public Verifier (`verifier`, default): Public verification portal with PII redaction.
2. University Registrar (`registrar`): Full lifecycle governance, issuance, registry, and revocation.
3. Compliance Auditor (`auditor`): Strictly read-only access to registry, audit ledger, exports, and anomaly lab.
"""

from enum import Enum
import hashlib
import hmac
from typing import Any, Callable, Dict, List, Optional

from fastapi import Depends, Request

from backend.core.config import settings


class Role(str, Enum):
    REGISTRAR = "registrar"
    VERIFIER = "verifier"
    AUDITOR = "auditor"


ACTOR_IDS: Dict[str, str] = {
    Role.REGISTRAR.value: "REGISTRAR-001",
    Role.AUDITOR.value: "AUDITOR-001",
    Role.VERIFIER.value: "PUBLIC-VERIFIER",
}


ROLE_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    Role.REGISTRAR.value: {
        "id": Role.REGISTRAR.value,
        "name": "University Registrar",
        "badge": "Registrar / Admin",
        "description": "Full lifecycle authority: issuance, credential registry, and revocation.",
        "avatar_icon": "admin_panel_settings",
        "badge_color": "emerald",
    },
    Role.VERIFIER.value: {
        "id": Role.VERIFIER.value,
        "name": "Public Verifier",
        "badge": "Public Verifier",
        "description": "Public trust verification portal with PII-redacted verification responses.",
        "avatar_icon": "verified_user",
        "badge_color": "indigo",
    },
    Role.AUDITOR.value: {
        "id": Role.AUDITOR.value,
        "name": "Compliance Auditor",
        "badge": "Compliance Auditor",
        "description": "Read-only forensic audit logging, registry inspection, and regulatory compliance.",
        "avatar_icon": "policy",
        "badge_color": "amber",
    },
}


class RBACUnauthorizedError(Exception):
    """Raised when an invalid Bearer API key is presented."""

    def __init__(self, message: str = "Invalid Bearer API key."):
        super().__init__(message)
        self.message = message


class RBACForbiddenError(Exception):
    """Raised when the current actor's role is not permitted for a route."""

    def __init__(self, required_roles: List[str], current_role: str):
        super().__init__(
            f"Role '{current_role}' is not authorized. Required: {', '.join(required_roles)}"
        )
        self.required_roles = required_roles
        self.current_role = current_role


def sign_role_cookie(role: str) -> str:
    """Create an HMAC-SHA256 signed cookie value for a valid role."""
    if role not in ROLE_DEFINITIONS:
        role = Role.VERIFIER.value
    mac = hmac.new(
        settings.SESSION_SECRET.encode("utf-8"),
        f"vericred_role:{role}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{role}.{mac}"


def verify_role_cookie(cookie_value: Optional[str]) -> str:
    """Verify an HMAC-SHA256 signed role cookie. Unsigned or tampered cookies resolve to verifier."""
    if not cookie_value or "." not in cookie_value:
        return Role.VERIFIER.value
    role_part, sig_part = cookie_value.split(".", 1)
    if role_part not in ROLE_DEFINITIONS:
        return Role.VERIFIER.value
    expected_mac = hmac.new(
        settings.SESSION_SECRET.encode("utf-8"),
        f"vericred_role:{role_part}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if hmac.compare_digest(sig_part, expected_mac):
        return role_part
    return Role.VERIFIER.value


def validate_relative_redirect(redirect: Optional[str], default: str = "/verify") -> str:
    """Validate that a redirect target is strictly a same-site relative path."""
    if not redirect:
        return default
    cleaned = redirect.strip()
    if (
        not cleaned.startswith("/")
        or cleaned.startswith("//")
        or cleaned.startswith("/\\")
        or "://" in cleaned
        or "\r" in cleaned
        or "\n" in cleaned
    ):
        return default
    return cleaned


def get_current_actor(request: Request) -> Dict[str, str]:
    """FastAPI dependency resolving the current actor {role, actor_id}.

    - Checks `Authorization: Bearer <key>` first (compared via `hmac.compare_digest`
      against `REGISTRAR_API_KEY` and `AUDITOR_API_KEY`; raises 401 if a Bearer key
      is presented and is invalid).
    - Otherwise verifies the HMAC-signed `vericred_role` cookie.
    - Defaults to `verifier` (`PUBLIC-VERIFIER`) when no valid credentials are present.
    - Never reads `?role=` query parameters.
    """
    auth_header = request.headers.get("Authorization")
    if auth_header is not None and auth_header.strip() != "":
        parts = auth_header.strip().split(None, 1)
        if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
            raise RBACUnauthorizedError("Invalid Authorization header format. Expected 'Bearer <key>'.")
        token = parts[1].strip()
        if settings.REGISTRAR_API_KEY and hmac.compare_digest(token, settings.REGISTRAR_API_KEY):
            actor = {
                "role": Role.REGISTRAR.value,
                "actor_id": ACTOR_IDS[Role.REGISTRAR.value],
            }
            request.state.actor = actor
            return actor
        if settings.AUDITOR_API_KEY and hmac.compare_digest(token, settings.AUDITOR_API_KEY):
            actor = {
                "role": Role.AUDITOR.value,
                "actor_id": ACTOR_IDS[Role.AUDITOR.value],
            }
            request.state.actor = actor
            return actor
        raise RBACUnauthorizedError("Invalid Bearer API key.")

    raw_cookie = request.cookies.get("vericred_role")
    role_id = verify_role_cookie(raw_cookie)
    actor = {
        "role": role_id,
        "actor_id": ACTOR_IDS[role_id],
    }
    request.state.actor = actor
    return actor


def require_role(*roles: str) -> Callable[..., Dict[str, str]]:
    """Build a FastAPI dependency requiring the current actor to have one of `*roles`."""
    allowed = [r.value if isinstance(r, Role) else str(r) for r in roles]

    def _enforce(actor: Dict[str, str] = Depends(get_current_actor)) -> Dict[str, str]:
        if actor["role"] not in allowed:
            raise RBACForbiddenError(required_roles=allowed, current_role=actor["role"])
        return actor

    return _enforce


def get_role_context(request: Request, actor: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Return dictionary of current role context and available roles for Jinja templates."""
    resolved_actor = actor or getattr(request.state, "actor", None) or get_current_actor(request)
    current_role_id = resolved_actor["role"]
    current_role = ROLE_DEFINITIONS.get(current_role_id, ROLE_DEFINITIONS[Role.VERIFIER.value])
    return {
        "current_role": current_role,
        "current_actor": resolved_actor,
        "roles": list(ROLE_DEFINITIONS.values()),
    }

