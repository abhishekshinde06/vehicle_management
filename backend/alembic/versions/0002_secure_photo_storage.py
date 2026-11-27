"""
Secure photo storage tracking and uniqueness constraints

Revision ID: 0002_secure_photo_storage
Revises: 0001_initial_schema
Create Date: 2026-11-26 00:00:00.000000 UTC
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Revision identifiers
revision: str = "0002_secure_photo_storage"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "uploaded_photos",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("uploader_id", sa.String(), nullable=False),
        sa.Column("photo_type", sa.String(), nullable=False),
        sa.Column("storage_type", sa.String(), nullable=False, server_default="local"),
        sa.Column("storage_reference", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("is_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fuel_entry_id", sa.String(), nullable=True),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["uploader_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["fuel_entry_id"], ["fuel_entries.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_reference", name="uq_uploaded_photos_storage_reference"),
    )
    op.create_index("ix_uploaded_photos_uploader_id", "uploaded_photos", ["uploader_id"], unique=False)
    op.create_index("ix_uploaded_photos_is_used", "uploaded_photos", ["is_used"], unique=False)
    op.create_index("ix_uploaded_photos_fuel_entry_id", "uploaded_photos", ["fuel_entry_id"], unique=False)

    with op.batch_alter_table("entry_photos") as batch_op:
        batch_op.add_column(sa.Column("uploaded_photo_id", sa.String(), nullable=True))
        batch_op.create_foreign_key(
            "fk_entry_photos_uploaded_photo_id",
            "uploaded_photos",
            ["uploaded_photo_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_unique_constraint(
            "uq_entry_photos_uploaded_photo_id",
            ["uploaded_photo_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("entry_photos") as batch_op:
        batch_op.drop_constraint("uq_entry_photos_uploaded_photo_id", type_="unique")
        batch_op.drop_constraint("fk_entry_photos_uploaded_photo_id", type_="foreignkey")
        batch_op.drop_column("uploaded_photo_id")

    op.drop_index("ix_uploaded_photos_fuel_entry_id", table_name="uploaded_photos")
    op.drop_index("ix_uploaded_photos_is_used", table_name="uploaded_photos")
    op.drop_index("ix_uploaded_photos_uploader_id", table_name="uploaded_photos")
    op.drop_table("uploaded_photos")
