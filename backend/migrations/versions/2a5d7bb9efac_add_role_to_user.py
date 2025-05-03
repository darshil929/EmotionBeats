"""Add role to user

Revision ID: 2a5d7bb9efac
Revises: 1bfc7ff9deb9
Create Date: 2025-04-27

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2a5d7bb9efac"
down_revision: Union[str, None] = "1bfc7ff9deb9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add role column to user table."""
    op.add_column(
        "user", sa.Column("role", sa.String(20), server_default="user", nullable=False)
    )


def downgrade() -> None:
    """Remove role column from user table."""
    op.drop_column("user", "role")
