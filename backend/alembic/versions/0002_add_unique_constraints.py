"""
Add unique constraints and indexes for concurrent duplicate prevention

Revision ID: 0002_add_unique_constraints
Revises: 0001_initial_schema
Create Date: 2026-11-25 00:00:00.000000 UTC

Adds:
1. Unique constraint and unique index on petrol_pumps.name
2. Unique constraint and unique index on petrol_pumps (latitude, longitude)
3. Composite index on fuel_entries (vehicle_id, current_odometer)
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_add_unique_constraints"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update petrol_pumps name index to be unique
    op.drop_index("ix_petrol_pumps_name", table_name="petrol_pumps")
    op.create_index("ix_petrol_pumps_name", "petrol_pumps", ["name"], unique=True)

    # 2. Add composite unique constraint on petrol_pumps (latitude, longitude)
    op.create_unique_constraint(
        "uq_petrol_pumps_lat_lon",
        "petrol_pumps",
        ["latitude", "longitude"]
    )

    # 3. Add composite index on fuel_entries (vehicle_id, current_odometer)
    op.create_index(
        "ix_fuel_entries_vehicle_odometer",
        "fuel_entries",
        ["vehicle_id", "current_odometer"],
        unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_fuel_entries_vehicle_odometer", table_name="fuel_entries")
    op.drop_constraint("uq_petrol_pumps_lat_lon", "petrol_pumps", type_="unique")
    op.drop_index("ix_petrol_pumps_name", table_name="petrol_pumps")
    op.create_index("ix_petrol_pumps_name", "petrol_pumps", ["name"], unique=False)
