"""bind uploaded photos to petrol pump

Revision ID: 0004_photo_pump_binding
Revises: 0003_petrol_pump_constraints
Create Date: 2026-11-26 12:12:59.767140+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# ---------------------------------------------------------------------------
# Revision identifiers, used by Alembic.
# ---------------------------------------------------------------------------
revision: str = '0004_photo_pump_binding'
down_revision: Union[str, None] = '0003_petrol_pump_constraints'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("uploaded_photos") as batch_op:

        batch_op.add_column(
            sa.Column(
                "petrol_pump_id",
                sa.String(),
                nullable=True
            )
        )

        batch_op.create_foreign_key(
            "fk_uploaded_photos_petrol_pump_id",
            "petrol_pumps",
            ["petrol_pump_id"],
            ["id"]
        )

        batch_op.create_index(
            "ix_uploaded_photos_petrol_pump_id",
            ["petrol_pump_id"],
            unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("uploaded_photos") as batch_op:

        batch_op.drop_index(
            "ix_uploaded_photos_petrol_pump_id"
        )

        batch_op.drop_constraint(
            "fk_uploaded_photos_petrol_pump_id",
            type_="foreignkey"
        )

        batch_op.drop_column("petrol_pump_id")