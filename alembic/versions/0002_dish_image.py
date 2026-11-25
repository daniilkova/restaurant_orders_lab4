"""Фото блюда в S3: колонка dishes.image_key

Revision ID: 0002_dish_image
Revises: 0001
"""
import sqlalchemy as sa

from alembic import op

revision = "0002_dish_image"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("dishes") as batch:
        batch.add_column(sa.Column("image_key", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("dishes") as batch:
        batch.drop_column("image_key")
