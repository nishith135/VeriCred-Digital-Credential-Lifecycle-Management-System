"""High-performance database loader for synthetic dataset.

Uses SQLAlchemy Core batch insertions against PostgreSQL via sync_engine.
Supports chunked batch loading (e.g. 2,000 records per chunk) to handle
full 20k/10k volume in seconds without memory pressure.
"""

import time
from typing import Any, Dict, List
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.core.database import sync_engine
from backend.generator.generator import SyntheticDataset
from backend.models import (
    AuditEvent,
    CompletionRecord,
    Course,
    Credential,
    CredentialRule,
    Issuer,
    Learner,
    Revocation,
    VerificationRequest,
)
from backend.services.ids import AUDIT_EVENT_SEQUENCE, CREDENTIAL_SEQUENCE, VERIFICATION_SEQUENCE

# (sequence, table, column, regex capturing the numeric part of the public ID)
PUBLIC_ID_SEQUENCES = [
    (CREDENTIAL_SEQUENCE, "credentials", "public_id", r"^CRD-\d{4}-(\d{6})$"),
    (VERIFICATION_SEQUENCE, "verification_requests", "public_id", r"^VER-\d{4}-(\d{6})$"),
    (AUDIT_EVENT_SEQUENCE, "audit_events", "event_id", r"^EVT-(\d{8})$"),
]


class DatabaseLoader:
    """Loads a SyntheticDataset into PostgreSQL using Core batch execution."""

    def __init__(self, dataset: SyntheticDataset, chunk_size: int = 2000):
        self.dataset = dataset
        self.chunk_size = chunk_size

    def load_all(self, truncate_first: bool = False) -> Dict[str, Any]:
        """Execute the batch ingestion in topological order.
        
        Returns:
            Dict containing execution duration and loaded row counts.
        """
        start_time = time.perf_counter()
        loaded_counts = {}

        with sync_engine.begin() as conn:
            if truncate_first:
                conn.execute(
                    text(
                        "TRUNCATE TABLE audit_events, verification_requests, revocations, "
                        "credentials, completion_records, credential_rules, learners, "
                        "courses, issuers RESTART IDENTITY CASCADE;"
                    )
                )

            # 1. Issuers
            loaded_counts["issuers"] = self._insert_batches(conn, Issuer.__table__, self.dataset.issuers)
            
            # 2. Courses
            loaded_counts["courses"] = self._insert_batches(conn, Course.__table__, self.dataset.courses)
            
            # 3. Credential Rules
            loaded_counts["rules"] = self._insert_batches(conn, CredentialRule.__table__, self.dataset.rules)
            
            # 4. Learners
            loaded_counts["learners"] = self._insert_batches(conn, Learner.__table__, self.dataset.learners)
            
            # 5. Completion Records
            loaded_counts["completions"] = self._insert_batches(conn, CompletionRecord.__table__, self.dataset.completions)
            
            # 6. Credentials
            loaded_counts["credentials"] = self._insert_batches(conn, Credential.__table__, self.dataset.credentials)
            
            # 7. Revocations
            loaded_counts["revocations"] = self._insert_batches(conn, Revocation.__table__, self.dataset.revocations)
            
            # 8. Verification Requests
            loaded_counts["verifications"] = self._insert_batches(conn, VerificationRequest.__table__, self.dataset.verifications)
            
            # 9. Audit Events
            loaded_counts["audit_events"] = self._insert_batches(conn, AuditEvent.__table__, self.dataset.audit_events)

            # Reset Postgres serial sequences so subsequent runtime API inserts don't collide with seed IDs
            for table_name in [
                "issuers", "courses", "credential_rules", "learners",
                "completion_records", "credentials", "revocations",
                "verification_requests", "audit_events"
            ]:
                conn.execute(
                    text(f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), coalesce(max(id), 1)) FROM {table_name};")
                )

            # Position public ID sequences so runtime numbering continues at max+1
            for seq_name, table_name, column, pattern in PUBLIC_ID_SEQUENCES:
                conn.execute(
                    text(
                        f"SELECT setval('{seq_name}', "
                        f"COALESCE(MAX(CAST(substring({column} FROM :pattern) AS BIGINT)), 0) + 1, false) "
                        f"FROM {table_name};"
                    ),
                    {"pattern": pattern},
                )

        duration = time.perf_counter() - start_time
        return {
            "duration_seconds": round(duration, 3),
            "loaded_counts": loaded_counts,
        }

    def _insert_batches(self, conn: Any, table: Any, records: List[Dict[str, Any]]) -> int:
        """Insert records in chunks using SQLAlchemy Core."""
        if not records:
            return 0

        total = len(records)
        for i in range(0, total, self.chunk_size):
            chunk = records[i : i + self.chunk_size]
            conn.execute(table.insert(), chunk)

        return total
