"""add append-only immutability trigger on audit_events

Revision ID: a4b1c2d3e4f5
Revises: 7c2e9a41b5d3
Create Date: 2026-10-30 06:25:00.000000+00:00

Adds a row-level BEFORE UPDATE OR DELETE trigger on audit_events that raises
an exception ('audit_events is append-only') to enforce ledger immutability
at the database level. INSERT and TRUNCATE operations remain unblocked.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a4b1c2d3e4f5"
down_revision: Union[str, None] = "7c2e9a41b5d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create trigger function
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_events_prevent_update_delete()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    # 2. Attach row-level BEFORE UPDATE OR DELETE trigger
    op.execute(
        """
        CREATE TRIGGER trg_audit_events_immutable
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW
        EXECUTE FUNCTION audit_events_prevent_update_delete();
        """
    )


def downgrade() -> None:
    # 1. Drop trigger
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_audit_events_immutable ON audit_events;
        """
    )
    # 2. Drop trigger function
    op.execute(
        """
        DROP FUNCTION IF EXISTS audit_events_prevent_update_delete();
        """
    )

