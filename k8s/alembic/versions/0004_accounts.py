"""ЛР8: роли client/moderator/admin, 2FA, профиль, подтверждение email, возрастная верификация

Revision ID: 0004_accounts
Revises: 0003_users_auth
"""
import sqlalchemy as sa

from alembic import op

revision = "0004_accounts"
down_revision = "0003_users_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("totp_secret", sa.String(64), nullable=True))
        batch.add_column(sa.Column("totp_enabled", sa.Boolean(), server_default=sa.false(), nullable=False))
        batch.add_column(sa.Column("display_name", sa.String(50), nullable=True))
        batch.add_column(sa.Column("avatar_key", sa.String(255), nullable=True))
        batch.add_column(sa.Column("username_changed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("is_email_verified", sa.Boolean(), server_default=sa.false(), nullable=False))
        batch.add_column(sa.Column("email_verification_token", sa.String(64), nullable=True))
        batch.add_column(sa.Column("email_verification_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("is_age_verified", sa.Boolean(), server_default=sa.false(), nullable=False))
        batch.add_column(sa.Column("age_verified_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(
            sa.Column("age_verification_required", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch.alter_column("role", server_default="client")
        batch.create_index("ix_users_email_verification_token", ["email_verification_token"])
    # Роль «user» из ЛР5 становится «client»; уже существующие учётки считаем подтверждёнными
    op.execute("UPDATE users SET role = 'client' WHERE role = 'user'")
    op.execute("UPDATE users SET is_email_verified = true")
    with op.batch_alter_table("dishes") as batch:
        batch.add_column(sa.Column("min_age", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    with op.batch_alter_table("dishes") as batch:
        batch.drop_column("min_age")
    op.execute("UPDATE users SET role = 'user' WHERE role IN ('client', 'moderator')")
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_email_verification_token")
        batch.alter_column("role", server_default="user")
        for col in ("age_verification_required", "age_verified_at", "is_age_verified",
                    "email_verification_expires_at", "email_verification_token", "is_email_verified",
                    "username_changed_at", "avatar_key", "display_name", "totp_enabled", "totp_secret"):
            batch.drop_column(col)
