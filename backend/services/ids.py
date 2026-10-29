"""Single source of truth for public identifier formats.

Formats (zero-padded, immutable, sequential):
    Issuer        ISS-00001
    Course        CRS-000001
    Learner       LRN-000001
    Completion    CMP-<learner public_id>-<course public_id>
    Credential    CRD-<year>-000001        (year from issued_at)
    Verification  VER-<year>-000001        (year from requested_at)
    Revocation    REV-<credential public_id>-01
    AuditEvent    EVT-00000001

The generator formats IDs from its deterministic indexes; runtime services
format IDs from Postgres sequences (see `next_sequence_value`) so concurrent
requests can never receive the same number.
"""

import re
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Postgres sequences created by migration 7c2e9a41b5d3
CREDENTIAL_SEQUENCE = "credential_public_seq"
VERIFICATION_SEQUENCE = "verification_public_seq"
AUDIT_EVENT_SEQUENCE = "audit_event_public_seq"

# Regexes used by the validator and tests to enforce formats
ID_PATTERNS: dict[str, re.Pattern[str]] = {
    "issuer": re.compile(r"^ISS-\d{5}$"),
    "course": re.compile(r"^CRS-\d{6}$"),
    "learner": re.compile(r"^LRN-\d{6}$"),
    "completion": re.compile(r"^CMP-LRN-\d{6}-CRS-\d{6}$"),
    "credential": re.compile(r"^CRD-\d{4}-\d{6}$"),
    "verification": re.compile(r"^VER-\d{4}-\d{6}$"),
    "revocation": re.compile(r"^REV-CRD-\d{4}-\d{6}-01$"),
    "audit_event": re.compile(r"^EVT-\d{8}$"),
}


def format_issuer_id(number: int) -> str:
    return f"ISS-{number:05d}"


def format_course_id(number: int) -> str:
    return f"CRS-{number:06d}"


def format_learner_id(number: int) -> str:
    return f"LRN-{number:06d}"


def format_completion_id(learner_pid: str, course_pid: str) -> str:
    return f"CMP-{learner_pid}-{course_pid}"


def format_credential_id(number: int, issued_at: datetime) -> str:
    return f"CRD-{issued_at.year}-{number:06d}"


def format_verification_id(number: int, requested_at: datetime) -> str:
    return f"VER-{requested_at.year}-{number:06d}"


def format_revocation_id(credential_pid: str) -> str:
    # A credential can be revoked at most once (unique FK), so the suffix is always 01.
    return f"REV-{credential_pid}-01"


def format_audit_event_id(number: int) -> str:
    return f"EVT-{number:08d}"


async def next_sequence_value(db: AsyncSession, sequence_name: str) -> int:
    """Fetch the next value from a whitelisted Postgres sequence (race-safe)."""
    if sequence_name not in (CREDENTIAL_SEQUENCE, VERIFICATION_SEQUENCE, AUDIT_EVENT_SEQUENCE):
        raise ValueError(f"Unknown public ID sequence: {sequence_name}")
    result = await db.execute(text(f"SELECT nextval('{sequence_name}')"))
    return int(result.scalar_one())
