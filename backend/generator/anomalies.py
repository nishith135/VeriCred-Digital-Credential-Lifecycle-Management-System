"""Seeded Anomaly Injection into Generated Baseline Dataset and Ground-Truth Registry.

Enforces MASTER_SPEC Section 11.5:
1. PREMATURE_ISSUANCE: issued_at earlier than completion_timestamp, validly hashed and signed -> INVALID_ISSUANCE.
2. DUPLICATE_CREDENTIAL_ID: staging rows in credential_import_staging.csv duplicating existing public_id -> REJECTED_DUPLICATE.
3. REVOKED_VERIFIES_AS_ACTIVE: Revocation row exists while credentials.status remains ACTIVE -> REVOKED.
4. ALTERED_PAYLOAD_NOT_DETECTED: half with payload_snapshot altered only, half with payload_snapshot and
   canonical_payload_hash altered together -> TAMPERED.

Ground-truth labels are stored only in exports/ground_truth.csv and exports/ground_truth.json
and are never added as columns to operational input tables or imported by issuance/verification services.
"""

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import timedelta
import json
from pathlib import Path
import random
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import pandas as pd

from backend.core.security import (
    compute_payload_hash,
    generate_deterministic_ed25519_keypair,
    sign_payload_hash,
)
from backend.services.ids import format_audit_event_id
from backend.services.payloads import build_credential_payload

if TYPE_CHECKING:
    from backend.generator.generator import SyntheticDataset

GROUND_TRUTH_COLUMNS = [
    "anomaly_id",
    "issue_type",
    "entity_public_id",
    "expected_outcome",
    "rule_reference",
]

STAGING_COLUMNS = [
    "id",
    "public_id",
    "completion_id",
    "issuer_id",
    "issued_at",
    "canonical_payload_hash",
    "issuer_signature",
    "payload_snapshot",
    "status",
    "created_at",
]


@dataclass
class GroundTruthEntry:
    anomaly_id: str
    issue_type: str
    entity_public_id: str
    expected_outcome: str
    rule_reference: str


def _resolve_private_keys(
    issuers_df: pd.DataFrame,
    seed: int = 20261022,
    explicit_keys: Optional[Dict[int, str]] = None,
) -> Dict[int, str]:
    """Retrieve issuer Ed25519 private keys from explicit dict, DataFrame attrs, or deterministic seed."""
    if explicit_keys:
        return explicit_keys
    attrs_keys = issuers_df.attrs.get("private_keys")
    if attrs_keys:
        return attrs_keys
    keys: Dict[int, str] = {}
    for row in issuers_df.to_dict("records"):
        idx = int(row["id"])
        seed_material = f"issuer_{idx}_seed_{seed}".encode("utf-8")
        priv_pem, _ = generate_deterministic_ed25519_keypair(seed_material)
        keys[idx] = priv_pem
    return keys


def inject_anomalies_df(
    credentials_df: pd.DataFrame,
    completions_df: pd.DataFrame,
    learners_df: pd.DataFrame,
    courses_df: pd.DataFrame,
    issuers_df: pd.DataFrame,
    verifications_df: pd.DataFrame,
    audit_events_df: pd.DataFrame,
    rng: random.Random,
    config: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """Stage 10: Inject the 4 mandatory anomaly scenarios into DataFrame tables using the seeded RNG.

    Returns:
        `pd.DataFrame` containing the ground_truth records, with updated DataFrames attached in
        `ground_truth_df.attrs["credentials_df"]`, `ground_truth_df.attrs["audit_events_df"]`, and
        `ground_truth_df.attrs["credential_import_staging_df"]`.
    """
    cfg = config or {}
    seed = int(cfg.get("seed", issuers_df.attrs.get("seed", 20261022)))
    private_keys = _resolve_private_keys(
        issuers_df,
        seed=seed,
        explicit_keys=cfg.get("issuer_private_keys"),
    )

    from backend.generator.generator import SyntheticDataset, REFERENCE_DATETIME, _records_to_df

    temp_ds = SyntheticDataset(
        seed=seed,
        scale=float(cfg.get("scale", 1.0)),
        reference_time=cfg.get("reference_time", REFERENCE_DATETIME),
        issuers=issuers_df.to_dict("records"),
        issuer_private_keys=private_keys,
        courses=courses_df.to_dict("records"),
        learners=learners_df.to_dict("records"),
        completions=completions_df.to_dict("records"),
        credentials=credentials_df.to_dict("records"),
        verifications=verifications_df.to_dict("records"),
        audit_events=audit_events_df.to_dict("records"),
    )
    inject_anomalies(temp_ds, rng)

    updated_creds_df = _records_to_df(temp_ds.credentials, list(credentials_df.columns))
    updated_audit_df = _records_to_df(temp_ds.audit_events, list(audit_events_df.columns))
    staging_df = _records_to_df(temp_ds.credential_import_staging, STAGING_COLUMNS)
    gt_df = _records_to_df(temp_ds.ground_truth, GROUND_TRUTH_COLUMNS)

    # Update input DataFrames in place so callers holding references see the injected mutations
    for col in updated_creds_df.columns:
        credentials_df[col] = updated_creds_df[col].values
    for col in updated_audit_df.columns:
        audit_events_df[col] = updated_audit_df[col].values

    gt_df.attrs["credentials_df"] = credentials_df
    gt_df.attrs["audit_events_df"] = audit_events_df
    gt_df.attrs["credential_import_staging_df"] = staging_df
    return gt_df


def inject_anomalies(
    dataset: "SyntheticDataset",
    rng: random.Random,
) -> List[Dict[str, Any]]:
    """Inject the 4 mandatory anomaly scenarios into the baseline dataset using the seeded RNG.

    Formula:
        n_per_type = max(2, round(len(dataset.credentials) * 0.002))
        (20 per type at full scale of 10,000 credentials).

    Modifies only the chosen target rows in-place and populates
    `dataset.credential_import_staging` and `dataset.ground_truth`.
    """
    n_creds = len(dataset.credentials)
    if n_creds == 0:
        return []

    n_per_type = max(2, round(n_creds * 0.002))

    comp_by_id = {c["id"]: c for c in dataset.completions}
    learner_by_id = {l["id"]: l for l in dataset.learners}
    course_by_id = {c["id"]: c for c in dataset.courses}
    issuer_by_id = {i["id"]: i for i in dataset.issuers}
    verified_cred_ids = {
        v["credential_id"] for v in dataset.verifications if v.get("credential_id") is not None
    }

    # Index CREDENTIAL_ISSUED audit events by target_entity_id for fast timestamp/hash sync
    issued_event_by_pub_id: Dict[str, Dict[str, Any]] = {
        ev["target_entity_id"]: ev
        for ev in dataset.audit_events
        if ev["event_type"] == "CREDENTIAL_ISSUED"
    }

    # Separate baseline revoked and active credentials (keep index 0 untouched so baseline index-0 checks stay clean)
    revoked_candidates = [
        c for c in dataset.credentials[1:] if c["status"] == "REVOKED"
    ]
    if len(revoked_candidates) < n_per_type:
        revoked_candidates = [c for c in dataset.credentials if c["status"] == "REVOKED"]

    unverified_revoked = [c for c in revoked_candidates if c["id"] not in verified_cred_ids]
    revoked_pool = unverified_revoked if len(unverified_revoked) >= n_per_type else revoked_candidates

    active_candidates = [
        c for c in dataset.credentials[1:] if c["status"] == "ACTIVE"
    ]
    unverified_active = [c for c in active_candidates if c["id"] not in verified_cred_ids]
    active_pool = (
        unverified_active if len(unverified_active) >= 3 * n_per_type else active_candidates
    )

    # Deterministically sample non-overlapping target sets using the seeded RNG
    chosen_active = rng.sample(active_pool, 3 * n_per_type)
    premature_targets = chosen_active[0:n_per_type]
    duplicate_targets = chosen_active[n_per_type : 2 * n_per_type]
    altered_targets = chosen_active[2 * n_per_type : 3 * n_per_type]
    stale_revoked_targets = rng.sample(revoked_pool, n_per_type)

    ground_truth: List[GroundTruthEntry] = []
    staging_rows: List[Dict[str, Any]] = []
    anomaly_seq = 1

    # -------------------------------------------------------------------------
    # 1. PREMATURE_ISSUANCE (issued_at < completion_timestamp, validly hashed & signed)
    # -------------------------------------------------------------------------
    for cred in premature_targets:
        comp = comp_by_id[cred["completion_id"]]
        learner = learner_by_id[comp["learner_id"]]
        course = course_by_id[comp["course_id"]]
        issuer = issuer_by_id[cred["issuer_id"]]
        priv_pem = dataset.issuer_private_keys[cred["issuer_id"]]

        premature_issued_at = comp["completion_timestamp"] - timedelta(
            days=rng.randint(2, 9),
            hours=rng.randint(1, 12),
        )
        claims = build_credential_payload(
            credential_id=cred["public_id"],
            issued_at=premature_issued_at,
            completion_timestamp=comp["completion_timestamp"],
            learner_id=learner["public_id"],
            learner_name=learner["full_name"],
            learner_email=learner["email"],
            course_code=course["public_id"],
            course_title=course["title"],
            assessment_score=comp["assessment_score"],
            assessment_status=comp["status"],
            issuer_id=issuer["public_id"],
            issuer_name=issuer["name"],
        )
        new_hash = compute_payload_hash(claims)
        new_sig = sign_payload_hash(priv_pem, new_hash)

        cred["issued_at"] = premature_issued_at
        cred["created_at"] = premature_issued_at
        cred["payload_snapshot"] = claims
        cred["canonical_payload_hash"] = new_hash
        cred["issuer_signature"] = new_sig

        ev = issued_event_by_pub_id.get(cred["public_id"])
        if ev is not None:
            ev["occurred_at"] = premature_issued_at
            details = dict(ev.get("details") or {})
            details["completion_id"] = cred["completion_id"]
            details["canonical_payload_hash"] = new_hash
            ev["details"] = details

        ground_truth.append(
            GroundTruthEntry(
                anomaly_id=f"ANM-{anomaly_seq:04d}",
                issue_type="PREMATURE_ISSUANCE",
                entity_public_id=cred["public_id"],
                expected_outcome="INVALID_ISSUANCE",
                rule_reference="MASTER_SPEC §6 / §11.5.1: Credential issued_at precedes completion_timestamp",
            )
        )
        anomaly_seq += 1

    # -------------------------------------------------------------------------
    # 2. DUPLICATE_CREDENTIAL_ID (staging rows duplicating existing public_id)
    # -------------------------------------------------------------------------
    issued_comp_ids = {c["completion_id"] for c in dataset.credentials}
    unissued_eligible_comps = [
        c
        for c in dataset.completions
        if c["id"] not in issued_comp_ids and c["status"] == "COMPLETED"
    ]
    if len(unissued_eligible_comps) < n_per_type:
        unissued_eligible_comps = list(dataset.completions[:n_per_type])

    for staging_idx, cred in enumerate(duplicate_targets, start=1):
        alt_comp = unissued_eligible_comps[(staging_idx - 1) % len(unissued_eligible_comps)]
        learner = learner_by_id[alt_comp["learner_id"]]
        course = course_by_id[alt_comp["course_id"]]
        issuer = issuer_by_id[cred["issuer_id"]]
        priv_pem = dataset.issuer_private_keys[cred["issuer_id"]]

        dup_issued_at = cred["issued_at"] + timedelta(hours=3)
        dup_claims = build_credential_payload(
            credential_id=cred["public_id"],
            issued_at=dup_issued_at,
            completion_timestamp=alt_comp["completion_timestamp"],
            learner_id=learner["public_id"],
            learner_name=learner["full_name"],
            learner_email=learner["email"],
            course_code=course["public_id"],
            course_title=course["title"],
            assessment_score=alt_comp["assessment_score"],
            assessment_status=alt_comp["status"],
            issuer_id=issuer["public_id"],
            issuer_name=issuer["name"],
        )
        dup_hash = compute_payload_hash(dup_claims)
        dup_sig = sign_payload_hash(priv_pem, dup_hash)

        staging_rows.append(
            {
                "id": staging_idx,
                "public_id": cred["public_id"],
                "completion_id": alt_comp["id"],
                "issuer_id": cred["issuer_id"],
                "issued_at": dup_issued_at,
                "canonical_payload_hash": dup_hash,
                "issuer_signature": dup_sig,
                "payload_snapshot": dup_claims,
                "status": "ACTIVE",
                "created_at": dup_issued_at,
            }
        )
        ground_truth.append(
            GroundTruthEntry(
                anomaly_id=f"ANM-{anomaly_seq:04d}",
                issue_type="DUPLICATE_CREDENTIAL_ID",
                entity_public_id=cred["public_id"],
                expected_outcome="REJECTED_DUPLICATE",
                rule_reference="MASTER_SPEC §7 / §11.5.2: Unique constraint on credentials.public_id rejects duplicate import",
            )
        )
        anomaly_seq += 1

    # -------------------------------------------------------------------------
    # 3. REVOKED_VERIFIES_AS_ACTIVE (Revocation row exists, credentials.status is ACTIVE)
    # -------------------------------------------------------------------------
    for cred in stale_revoked_targets:
        cred["status"] = "ACTIVE"
        ground_truth.append(
            GroundTruthEntry(
                anomaly_id=f"ANM-{anomaly_seq:04d}",
                issue_type="REVOKED_VERIFIES_AS_ACTIVE",
                entity_public_id=cred["public_id"],
                expected_outcome="REVOKED",
                rule_reference="MASTER_SPEC §8 / §11.5.3: Revocation table overrides stale ACTIVE credential status",
            )
        )
        anomaly_seq += 1

    # -------------------------------------------------------------------------
    # 4. ALTERED_PAYLOAD_NOT_DETECTED (half snapshot-only, half snapshot + hash)
    # -------------------------------------------------------------------------
    half = n_per_type // 2
    for idx, cred in enumerate(altered_targets):
        tampered_snapshot = deepcopy(cred["payload_snapshot"])
        orig_score = float(tampered_snapshot["assessment"]["score"])
        new_score = round(min(99.99, orig_score + 0.37) if orig_score < 99.50 else orig_score - 5.25, 2)
        tampered_snapshot["assessment"]["score"] = new_score
        tampered_snapshot["course"]["title"] = f"{tampered_snapshot['course']['title']} [Tampered]"
        cred["payload_snapshot"] = tampered_snapshot

        if idx < half:
            # First half: payload_snapshot altered only (canonical_payload_hash & signature unchanged)
            rule_ref = (
                "MASTER_SPEC §8 / §11.5.4a: Payload snapshot altered without updating canonical_payload_hash"
            )
        else:
            # Second half: payload_snapshot AND canonical_payload_hash altered together
            recomputed_hash = compute_payload_hash(tampered_snapshot)
            cred["canonical_payload_hash"] = recomputed_hash
            ev = issued_event_by_pub_id.get(cred["public_id"])
            if ev is not None:
                details = dict(ev.get("details") or {})
                details["completion_id"] = cred["completion_id"]
                details["canonical_payload_hash"] = recomputed_hash
                ev["details"] = details
            rule_ref = (
                "MASTER_SPEC §8 / §11.5.4b: Payload snapshot and canonical_payload_hash altered together"
            )

        ground_truth.append(
            GroundTruthEntry(
                anomaly_id=f"ANM-{anomaly_seq:04d}",
                issue_type="ALTERED_PAYLOAD_NOT_DETECTED",
                entity_public_id=cred["public_id"],
                expected_outcome="TAMPERED",
                rule_reference=rule_ref,
            )
        )
        anomaly_seq += 1

    # Re-sort audit events chronologically after premature issuance timestamp adjustments
    dataset.audit_events.sort(key=lambda e: (e["occurred_at"], e["id"]))
    for idx, event in enumerate(dataset.audit_events, start=1):
        event["id"] = idx
        event["event_id"] = format_audit_event_id(idx)

    gt_dicts = [asdict(entry) for entry in ground_truth]
    dataset.credential_import_staging = staging_rows
    dataset.ground_truth = gt_dicts
    return gt_dicts


def load_ground_truth(exports_dir: Path = Path("./exports")) -> List[Dict[str, Any]]:
    """Load ground-truth records from `<exports_dir>/ground_truth.json`."""
    gt_path = exports_dir / "ground_truth.json"
    if not gt_path.exists():
        return []
    with open(gt_path, "r", encoding="utf-8") as f:
        return json.load(f)
