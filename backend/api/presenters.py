"""Presentation Layer for VeriCred.

Centralizes user-facing labels, status tones, icons, human-readable descriptions,
and non-technical check explanations for the Public Verification portal and Anomaly Lab.
Ensures templates and views perform no hardcoded outcome logic or technical string comparisons.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union

# =============================================================================
# 1. Outcome Metadata & Presentation Mappings
# =============================================================================

OUTCOME_PRESENTATION: Dict[str, Dict[str, str]] = {
    "VALID": {
        "label": "Valid",
        "tone": "success",
        "icon": "verified",
        "headline": "Valid — Authentic Credential Verified",
        "summary": "This credential is authentic, unaltered and actively recognized in the registry.",
    },
    "REVOKED": {
        "label": "Revoked",
        "tone": "danger",
        "icon": "gavel",
        "headline": "Revoked",
        "summary": "This credential has been revoked by the issuing authority and is no longer active.",
    },
    "TAMPERED": {
        "label": "Altered",
        "tone": "warning",
        "icon": "security_update_warning",
        "headline": "Altered — Content Mismatch",
        "summary": "The presented credential details do not match what was originally issued.",
    },
    "INVALID_ISSUANCE": {
        "label": "Invalid issuance",
        "tone": "danger",
        "icon": "error",
        "headline": "Invalid issuance — Requirement Violation",
        "summary": "This credential violates academic completion chronology or issuer requirements.",
    },
    "NOT_FOUND": {
        "label": "Not found",
        "tone": "neutral",
        "icon": "search_off",
        "headline": "Not found — No Credential Located",
        "summary": "We could not find any credential matching this identifier in the registry.",
    },
    "REJECTED_DUPLICATE": {
        "label": "Rejected as duplicate",
        "tone": "danger",
        "icon": "block",
        "headline": "Rejected as duplicate",
        "summary": "Import was rejected because this credential identifier already exists.",
    },
}

TONE_CLASSES: Dict[str, Dict[str, str]] = {
    "success": {
        "badge": "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40",
        "card_border": "border-emerald-500/40",
        "icon_bg": "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30",
        "text": "text-emerald-400",
        "pulse": "bg-emerald-400 veri-pulse",
    },
    "danger": {
        "badge": "bg-rose-500/20 text-rose-300 border border-rose-500/40",
        "card_border": "border-rose-500/40",
        "icon_bg": "bg-rose-500/10 text-rose-400 border border-rose-500/30",
        "text": "text-rose-400",
        "pulse": "bg-rose-400",
    },
    "warning": {
        "badge": "bg-amber-500/20 text-amber-300 border border-amber-500/40",
        "card_border": "border-amber-500/40",
        "icon_bg": "bg-amber-500/10 text-amber-400 border border-amber-500/30",
        "text": "text-amber-400",
        "pulse": "bg-amber-400",
    },
    "neutral": {
        "badge": "bg-elevated text-text-muted border border-border",
        "card_border": "border-border",
        "icon_bg": "bg-elevated text-text-muted border border-border",
        "text": "text-text-muted",
        "pulse": "bg-slate-500",
    },
}


def format_human_datetime(val: Any) -> str:
    """Format timestamps for humans: e.g. '30 Oct 2026, 06:30 UTC'."""
    if not val:
        return "—"
    if isinstance(val, str):
        try:
            val = datetime.fromisoformat(val.replace("Z", "+00:00"))
        except Exception:
            return val
    if isinstance(val, (datetime, date)):
        return val.strftime("%d %b %Y, %H:%M UTC")
    return str(val)


def format_human_date(val: Any) -> str:
    """Format dates for humans: e.g. '29 Oct 2023'."""
    if not val:
        return "—"
    if isinstance(val, str):
        try:
            val = datetime.fromisoformat(val.replace("Z", "+00:00"))
        except Exception:
            return val
    if isinstance(val, (datetime, date)):
        return val.strftime("%d %b %Y")
    return str(val)


def to_sentence_case(val: Any) -> str:
    """Format enum strings into clean sentence case: e.g. 'ADMINISTRATIVE_ERROR' -> 'Administrative error'."""
    if not val:
        return ""
    s = str(val).replace("_", " ").strip()
    if not s:
        return ""
    return s[0].upper() + s[1:].lower()


# =============================================================================
# 2. Verification Presenter
# =============================================================================

class VerificationPresenter:
    """Presents verification results with plain-language checks and strict role redaction."""

    @classmethod
    def present(
        cls,
        result: Any,
        actor_role: str = "verifier",
    ) -> Dict[str, Any]:
        outcome_raw = getattr(result, "outcome", None) or (result.get("outcome") if isinstance(result, dict) else "NOT_FOUND")
        meta = OUTCOME_PRESENTATION.get(outcome_raw, OUTCOME_PRESENTATION["NOT_FOUND"])
        tone = meta["tone"]
        tone_classes = TONE_CLASSES.get(tone, TONE_CLASSES["neutral"])

        # Identifiers and timestamps
        cred_id = getattr(result, "credential_public_id", None) or (result.get("credential_public_id") if isinstance(result, dict) else "")
        ref_id = getattr(result, "verification_id", None) or (result.get("verification_id") if isinstance(result, dict) else None)
        timestamp = getattr(result, "timestamp", None) or (result.get("timestamp") if isinstance(result, dict) else None)
        issued_at = getattr(result, "issued_at", None) or (result.get("issued_at") if isinstance(result, dict) else None)
        issuer_name = getattr(result, "issuer_name", None) or (result.get("issuer_name") if isinstance(result, dict) else None)
        course_title = getattr(result, "course_title", None) or (result.get("course_title") if isinstance(result, dict) else None)
        holder_masked = getattr(result, "holder_masked", None) or (result.get("holder_masked") if isinstance(result, dict) else None)

        # Factors
        factors = getattr(result, "factors", None) or (result.get("factors") if isinstance(result, dict) else None)
        record_found = getattr(factors, "record_found", True) if factors else True
        payload_hash_matches = getattr(factors, "payload_hash_matches", True) if factors else True
        issuer_authenticated = getattr(factors, "issuer_authenticated", True) if factors else True
        is_revoked = getattr(factors, "is_revoked", False) if factors else False
        eligibility_valid = getattr(factors, "eligibility_valid", True) if factors else True

        # Revocation details
        rev_details = getattr(result, "revocation_details", None) or (result.get("revocation_details") if isinstance(result, dict) else None)
        rev_date_raw = None
        rev_reason_raw = None
        revoked_by = None
        rev_notes = None

        if rev_details:
            rev_date_raw = rev_details.get("revocation_timestamp")
            rev_reason_raw = rev_details.get("reason_code")
            revoked_by = rev_details.get("revoked_by_actor_id")
            rev_notes = rev_details.get("notes")
        else:
            rev_date_raw = getattr(result, "revoked_at", None) or (result.get("revoked_at") if isinstance(result, dict) else None)
            rev_reason_raw = getattr(result, "reason_code", None) or (result.get("reason_code") if isinstance(result, dict) else None)

        rev_date_fmt = format_human_date(rev_date_raw) if rev_date_raw else None
        rev_datetime_fmt = format_human_datetime(rev_date_raw) if rev_date_raw else None
        rev_reason_sentence = to_sentence_case(rev_reason_raw) if rev_reason_raw else "Not specified"

        # Construct headline
        if outcome_raw == "REVOKED":
            headline = f"Revoked on {rev_date_fmt}. Reason: {rev_reason_sentence}" if rev_date_fmt else f"Revoked. Reason: {rev_reason_sentence}"
        else:
            headline = meta["headline"]

        # Staff full credential snapshot
        cred_details = getattr(result, "credential_details", None) or (result.get("credential_details") if isinstance(result, dict) else None)
        staff_snapshot = None
        technical_details = None

        is_staff = actor_role in ("registrar", "auditor")
        if is_staff and cred_details:
            staff_snapshot = cred_details.get("payload_snapshot")
            # Collapsed technical details for staff only
            payload_hash = cred_details.get("canonical_payload_hash")
            signature = cred_details.get("issuer_signature")
            if payload_hash or signature:
                technical_details = {
                    "payload_hash": payload_hash,
                    "signature": signature,
                }

        # 4 Human Verification Checks (+ Completion requirements check)
        checks = [
            {
                "label": "Record found",
                "description": "This credential exists in the registry.",
                "passed": record_found,
                "icon": "check_circle" if record_found else "cancel",
                "text_class": "text-emerald-400" if record_found else "text-rose-400",
            },
            {
                "label": "Content unchanged",
                "description": "The credential details match what was issued.",
                "passed": payload_hash_matches,
                "icon": "check_circle" if payload_hash_matches else "warning",
                "text_class": "text-emerald-400" if payload_hash_matches else "text-amber-400",
            },
            {
                "label": f"Issued by {issuer_name}" if issuer_name else "Issued by accredited institution",
                "description": "The issuer's signature is valid.",
                "passed": issuer_authenticated,
                "icon": "check_circle" if issuer_authenticated else "cancel",
                "text_class": "text-emerald-400" if issuer_authenticated else "text-rose-400",
            },
            {
                "label": "Revoked" if is_revoked else "Not revoked",
                "description": f"Revoked on {rev_date_fmt}. Reason: {rev_reason_sentence}." if is_revoked else "This credential has not been revoked.",
                "passed": not is_revoked,
                "icon": "check_circle" if not is_revoked else "gavel",
                "text_class": "text-emerald-400" if not is_revoked else "text-rose-400",
            },
        ]

        completion_check = {
            "label": "Completion requirements met",
            "description": "All academic completion criteria and dates were satisfied." if eligibility_valid else "Completion criteria or date rules were not satisfied.",
            "passed": eligibility_valid,
            "icon": "check_circle" if eligibility_valid else "cancel",
            "text_class": "text-emerald-400" if eligibility_valid else "text-rose-400",
        }

        return {
            "outcome": outcome_raw,
            "outcome_label": meta["label"],
            "tone": tone,
            "tone_classes": tone_classes,
            "icon": meta["icon"],
            "headline": headline,
            "summary": meta["summary"],
            "credential_public_id": cred_id,
            "reference_id": ref_id,
            "verified_at": format_human_datetime(timestamp) if timestamp else None,
            "issued_at": format_human_datetime(issued_at) if issued_at else None,
            "holder_masked": holder_masked,
            "course_title": course_title,
            "issuer_name": issuer_name,
            "checks": checks,
            "completion_check": completion_check,
            "is_revoked": is_revoked,
            "revocation": {
                "date": rev_datetime_fmt,
                "reason": rev_reason_sentence,
                "reason_code": rev_reason_raw,
                "authorized_by": revoked_by,
                "notes": rev_notes,
            } if is_revoked else None,
            "staff_snapshot": staff_snapshot,
            "technical_details": technical_details,
            "is_staff": is_staff,
            "is_not_found": outcome_raw == "NOT_FOUND",
        }


# =============================================================================
# 3. Anomaly Presenter
# =============================================================================

ANOMALY_SCENARIOS_HUMAN: Dict[str, Dict[str, str]] = {
    "PREMATURE_ISSUANCE": {
        "title": "Credential issued before course completion",
        "description": "Checks that a credential dated earlier than the learner's completion is flagged.",
        "expected_outcome": "INVALID_ISSUANCE",
    },
    "DUPLICATE_CREDENTIAL_ID": {
        "title": "Duplicate credential ID",
        "description": "Checks that importing a credential with an ID that already exists is rejected.",
        "expected_outcome": "REJECTED_DUPLICATE",
    },
    "REVOKED_VERIFIES_AS_ACTIVE": {
        "title": "Revoked credential still marked active",
        "description": "Checks that a credential with a revocation record shows as revoked even if its status was never updated.",
        "expected_outcome": "REVOKED",
    },
    "ALTERED_PAYLOAD_NOT_DETECTED": {
        "title": "Credential altered after issuance",
        "description": "Checks that changes to a credential's details are detected, including when its stored fingerprint was changed to match.",
        "expected_outcome": "TAMPERED",
    },
}


class AnomalyPresenter:
    """Formats Anomaly Lab scenarios with plain language, human outcomes, and equal-height layout."""

    @classmethod
    def present_card(cls, card_data: Dict[str, Any]) -> Dict[str, Any]:
        scenario_id = card_data.get("scenario_id", "")
        meta = ANOMALY_SCENARIOS_HUMAN.get(scenario_id, {
            "title": card_data.get("title", scenario_id),
            "description": card_data.get("description", ""),
            "expected_outcome": card_data.get("expected_outcome", ""),
        })

        passed = card_data.get("passed")
        if passed is True:
            status_text = "Passed"
            status_tone = "success"
        elif passed is False:
            status_text = "Failed"
            status_tone = "danger"
        else:
            status_text = "Not run yet"
            status_tone = "neutral"

        expected_raw = meta["expected_outcome"]
        actual_raw = card_data.get("actual_outcome", "")

        expected_label = OUTCOME_PRESENTATION.get(expected_raw, {}).get("label", expected_raw)
        actual_label = OUTCOME_PRESENTATION.get(actual_raw, {}).get("label", actual_raw if actual_raw != "Not run yet" else "—")

        # Stacked example & detection numbers
        ex_id = card_data.get("example_entity_id")
        example_credential = ex_id if ex_id and ex_id != "Not run yet" else "—"

        num = card_data.get("numerator")
        den = card_data.get("denominator")
        if passed is not None and den is not None and den > 0:
            detected_display = f"{num} of {den}"
        else:
            detected_display = "—"

        return {
            "scenario_id": scenario_id,
            "title": meta["title"],
            "description": meta["description"],
            "example_credential": example_credential,
            "detected_display": detected_display,
            "expected_outcome_label": expected_label,
            "actual_outcome_label": actual_label,
            "passed": passed,
            "status_text": status_text,
            "status_tone": status_tone,
            "status_classes": TONE_CLASSES.get(status_tone, TONE_CLASSES["neutral"]),
            "elapsed_ms": card_data.get("elapsed_ms"),
            "trace": card_data.get("trace"),
        }

