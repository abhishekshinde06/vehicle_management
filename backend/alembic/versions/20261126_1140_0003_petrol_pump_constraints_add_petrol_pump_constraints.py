"""Add petrol pump uniqueness constraints."""

from alembic import context, op
import sqlalchemy as sa


revision = "0003_petrol_pump_constraints"
down_revision = "0002_secure_photo_storage"
branch_labels = None
depends_on = None


def upgrade():
    if not context.is_offline_mode():
        connection = op.get_bind()

        # Check existing duplicate names
        duplicate_names = connection.execute(
            sa.text("""
                SELECT LOWER(TRIM(name)), COUNT(*)
                FROM petrol_pumps
                GROUP BY LOWER(TRIM(name))
                HAVING COUNT(*) > 1
            """)
        ).fetchall()

        if duplicate_names:
            raise RuntimeError(
                f"Duplicate petrol pump names found: {duplicate_names}"
            )

        # Check existing duplicate GPS coordinates
        duplicate_locations = connection.execute(
            sa.text("""
                SELECT latitude, longitude, COUNT(*)
                FROM petrol_pumps
                GROUP BY latitude, longitude
                HAVING COUNT(*) > 1
            """)
        ).fetchall()

        if duplicate_locations:
            raise RuntimeError(
                f"Duplicate pump locations found: {duplicate_locations}"
            )

    # SQLite and PostgreSQL compatible constraint
    with op.batch_alter_table("petrol_pumps") as batch_op:
        batch_op.drop_index("ix_petrol_pumps_name")

        batch_op.create_unique_constraint(
            "uq_petrol_pumps_lat_lon",
            ["latitude", "longitude"]
        )

    # Case-insensitive unique name index
    op.create_index(
        "uq_petrol_pumps_name_ci",
        "petrol_pumps",
        [sa.text("lower(trim(name))")],
        unique=True
    )


def downgrade():
    op.drop_index(
        "uq_petrol_pumps_name_ci",
        table_name="petrol_pumps"
    )

    with op.batch_alter_table("petrol_pumps") as batch_op:
        batch_op.drop_constraint(
            "uq_petrol_pumps_lat_lon",
            type_="unique"
        )

        batch_op.create_index(
            "ix_petrol_pumps_name",
            ["name"],
            unique=False
        )