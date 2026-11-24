"""
Initial schema — users, vehicles, petrol_pumps, fuel_entries, entry_photos, audit_logs

Revision ID: 0001_initial_schema
Revises: —
Create Date: 2026-11-23 00:00:00.000000 UTC

This migration creates the full initial schema from the existing SQLAlchemy
models.  It is intentionally written as explicit DDL (rather than autogenerate
output) so it can be reviewed and understood at a glance.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # ------------------------------------------------------------------
    # vehicles
    # ------------------------------------------------------------------
    op.create_table(
        "vehicles",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("vehicle_number", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("initial_odometer", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vehicles_vehicle_number", "vehicles", ["vehicle_number"], unique=True)

    # ------------------------------------------------------------------
    # petrol_pumps
    # ------------------------------------------------------------------
    op.create_table(
        "petrol_pumps",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("radius_meters", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_petrol_pumps_name", "petrol_pumps", ["name"], unique=False)

    # ------------------------------------------------------------------
    # fuel_entries
    # ------------------------------------------------------------------
    op.create_table(
        "fuel_entries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("vehicle_id", sa.String(), nullable=False),
        sa.Column("petrol_pump_id", sa.String(), nullable=False),
        sa.Column("operator_id", sa.String(), nullable=False),
        sa.Column("current_odometer", sa.Float(), nullable=False),
        sa.Column("previous_odometer", sa.Float(), nullable=False),
        sa.Column("fuel_litres", sa.Float(), nullable=False),
        sa.Column("is_full_tank", sa.Boolean(), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("mileage_kmpl", sa.Float(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("accuracy_m", sa.Float(), nullable=True),
        sa.Column("distance_from_pump_m", sa.Float(), nullable=True),
        sa.Column("is_location_verified", sa.Boolean(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("rejection_reason", sa.String(), nullable=True),
        sa.Column("reviewed_by", sa.String(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["petrol_pump_id"], ["petrol_pumps.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fuel_entries_vehicle_id", "fuel_entries", ["vehicle_id"], unique=False)
    op.create_index("ix_fuel_entries_petrol_pump_id", "fuel_entries", ["petrol_pump_id"], unique=False)
    op.create_index("ix_fuel_entries_status", "fuel_entries", ["status"], unique=False)

    # ------------------------------------------------------------------
    # entry_photos
    # ------------------------------------------------------------------
    op.create_table(
        "entry_photos",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("fuel_entry_id", sa.String(), nullable=False),
        sa.Column("photo_type", sa.String(), nullable=False),
        sa.Column("photo_url", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["fuel_entry_id"], ["fuel_entries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_entry_photos_fuel_entry_id", "entry_photos", ["fuel_entry_id"], unique=False)

    # ------------------------------------------------------------------
    # audit_logs
    # ------------------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("fuel_entry_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("performed_by", sa.String(), nullable=False),
        sa.Column("remarks", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["fuel_entry_id"], ["fuel_entries.id"]),
        sa.ForeignKeyConstraint(["performed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_fuel_entry_id", "audit_logs", ["fuel_entry_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_logs_fuel_entry_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_entry_photos_fuel_entry_id", table_name="entry_photos")
    op.drop_table("entry_photos")

    op.drop_index("ix_fuel_entries_status", table_name="fuel_entries")
    op.drop_index("ix_fuel_entries_petrol_pump_id", table_name="fuel_entries")
    op.drop_index("ix_fuel_entries_vehicle_id", table_name="fuel_entries")
    op.drop_table("fuel_entries")

    op.drop_index("ix_petrol_pumps_name", table_name="petrol_pumps")
    op.drop_table("petrol_pumps")

    op.drop_index("ix_vehicles_vehicle_number", table_name="vehicles")
    op.drop_table("vehicles")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
