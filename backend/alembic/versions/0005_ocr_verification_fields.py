"""Add OCR verification fields to fuel_entries

Revision ID: 0005_ocr_verification_fields
Revises: 0004_photo_pump_binding
Create Date: 2026-11-26 18:55:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision: str = "0005_ocr_verification_fields"
down_revision: Union[str, None] = "0004_photo_pump_binding"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("fuel_entries") as batch_op:
        batch_op.add_column(sa.Column("ocr_odometer_status", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("ocr_odometer_value", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("ocr_fuel_status", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("ocr_fuel_value", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "needs_manual_review",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(sa.Column("ocr_notes", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("fuel_entries") as batch_op:
        batch_op.drop_column("ocr_notes")
        batch_op.drop_column("needs_manual_review")
        batch_op.drop_column("ocr_fuel_value")
        batch_op.drop_column("ocr_fuel_status")
        batch_op.drop_column("ocr_odometer_value")
        batch_op.drop_column("ocr_odometer_status")
