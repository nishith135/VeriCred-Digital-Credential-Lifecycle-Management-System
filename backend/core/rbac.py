"""Role-Based Access Control (RBAC) Module for VeriCred.

Defines the roles, permissions, and helper utilities for:
1. Public Verifier: Can query credential authenticity and inspect anomalies.
2. University Registrar (Admin): Can manage the credential registry and execute revocations.
3. Compliance Auditor: Can review the immutable audit ledger and export forensic records.
"""

from enum import Enum
from typing import Any, Dict
from fastapi import Request


class Role(str, Enum):
    REGISTRAR = "registrar"
    VERIFIER = "verifier"
    AUDITOR = "auditor"


ROLE_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    Role.REGISTRAR.value: {
        "id": Role.REGISTRAR.value,
        "name": "University Registrar",
        "badge": "Registrar / Admin",
        "description": "Full lifecycle authority: issuance, credential registry, and revocation.",
        "can_revoke": True,
        "can_export": True,
        "can_inspect_audit": True,
        "avatar_icon": "admin_panel_settings",
        "badge_color": "emerald",
    },
    Role.VERIFIER.value: {
        "id": Role.VERIFIER.value,
        "name": "Public Verifier",
        "badge": "Public Verifier",
        "description": "Public trust verification portal and anomaly stress-test lab.",
        "can_revoke": False,
        "can_export": False,
        "can_inspect_audit": False,
        "avatar_icon": "verified_user",
        "badge_color": "indigo",
    },
    Role.AUDITOR.value: {
        "id": Role.AUDITOR.value,
        "name": "Compliance Auditor",
        "badge": "Compliance Auditor",
        "description": "Forensic audit logging, export verification, and regulatory compliance.",
        "can_revoke": False,
        "can_export": True,
        "can_inspect_audit": True,
        "avatar_icon": "policy",
        "badge_color": "amber",
    },
}


def get_current_role(request: Request) -> str:
    """Extract current user role from cookie or query param, defaulting to registrar."""
    role_param = request.query_params.get("role")
    if role_param in ROLE_DEFINITIONS:
        return role_param
    cookie_role = request.cookies.get("vericred_role")
    if cookie_role in ROLE_DEFINITIONS:
        return cookie_role
    return Role.REGISTRAR.value


def get_role_context(request: Request) -> Dict[str, Any]:
    """Return dictionary of current role context and available roles for Jinja templates."""
    current_role_id = get_current_role(request)
    current_role = ROLE_DEFINITIONS.get(current_role_id, ROLE_DEFINITIONS[Role.REGISTRAR.value])
    return {
        "current_role": current_role,
        "roles": list(ROLE_DEFINITIONS.values()),
        "is_registrar": current_role["can_revoke"],
        "is_auditor": current_role["can_inspect_audit"],
    }
