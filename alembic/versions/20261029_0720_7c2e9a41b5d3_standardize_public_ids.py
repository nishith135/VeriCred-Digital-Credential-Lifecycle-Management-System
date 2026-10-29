"""standardize public ids: completion/revocation public_id and numbering sequences

Revision ID: 7c2e9a41b5d3
Revises: 3891f21a6ba9
Create Date: 2026-10-29 07:20:00.000000+00:00

- Adds public_id to completion_records (CMP-<learner>-<course>) and
  revocations (REV-<credential>-01), backfilled from parent public_ids so the
  migration is safe on a populated database, then made NOT NULL + unique.
  Pre-existing duplicate (learner, course) pairs keep the canonical ID on the
  lowest id row and receive a -02, -03 ... suffix on later rows; the dataset
  validator reports those rows as format violations.
- Creates Postgres sequences used by runtime services for race-safe
  credential, verification, and audit event numbering. Each sequence starts
  after the highest number already present in the new format.
- No CHECK constraints on formats: legacy CRED-/VRF- rows must remain valid.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7c2e9a41b5d3"
down_revision: Union[str, None] = "3891f21a6ba9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (sequence name, table, column, regex capturing the numeric part)
SEQUENCES = [
    ("credential_public_seq", "credentials", "public_id", r"^CRD-\d{4}-(\d{6})$"),
    ("verification_public_seq", "verification_requests", "public_id", r"^VER-\d{4}-(\d{6})$"),
    ("audit_event_public_seq", "audit_events", "event_id", r"^EVT-(\d{8})$"),
]


def upgrade() -> None:
    # 1. completion_records.public_id
    op.add_column("completion_records", sa.Column("public_id", sa.String(length=64), nullable=True))
    op.execute(
        """
        UPDATE completion_records AS cr
        SET public_id = numbered.base || CASE WHEN numbered.rn = 1 THEN ''
                                              ELSE '-' || lpad(numbered.rn::text, 2, '0') END
        FROM (
            SELECT c.id,
                   'CMP-' || l.public_id || '-' || co.public_id AS base,
                   row_number() OVER (PARTITION BY c.learner_id, c.course_id ORDER BY c.id) AS rn
            FROM completion_records c
            JOIN learners l ON l.id = c.learner_id
            JOIN courses co ON co.id = c.course_id
        ) AS numbered
        WHERE cr.id = numbered.id
        """
    )
    op.alter_column("completion_records", "public_id", nullable=False)
    op.create_index(
        op.f("ix_completion_records_public_id"), "completion_records", ["public_id"], unique=True
    )

    # 2. revocations.public_id (credential_id is unique, so suffix 01 never collides)
    op.add_column("revocations", sa.Column("public_id", sa.String(length=64), nullable=True))
    op.execute(
        """
        UPDATE revocations AS r
        SET public_id = 'REV-' || c.public_id || '-01'
        FROM credentials c
        WHERE c.id = r.credential_id
        """
    )
    op.alter_column("revocations", "public_id", nullable=False)
    op.create_index(op.f("ix_revocations_public_id"), "revocations", ["public_id"], unique=True)

    # 3. Numbering sequences, positioned after any existing new-format numbers
    for seq_name, table, column, pattern in SEQUENCES:
        op.execute(f"CREATE SEQUENCE {seq_name} START WITH 1 INCREMENT BY 1 MINVALUE 1")
        op.execute(
            f"""
            SELECT setval(
                '{seq_name}',
                COALESCE(MAX(CAST(substring({column} FROM '{pattern}') AS BIGINT)), 0) + 1,
                false
            )
            FROM {table}
            """
        )


def downgrade() -> None:
    for seq_name, _table, _column, _pattern in reversed(SEQUENCES):
        op.execute(f"DROP SEQUENCE IF EXISTS {seq_name}")

    op.drop_index(op.f("ix_revocations_public_id"), table_name="revocations")
    op.drop_column("revocations", "public_id")

    op.drop_index(op.f("ix_completion_records_public_id"), table_name="completion_records")
    op.drop_column("completion_records", "public_id")

