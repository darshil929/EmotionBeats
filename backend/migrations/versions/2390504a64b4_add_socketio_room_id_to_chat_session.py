"""add_socketio_room_id_to_chat_session

Revision ID: 2390504a64b4
Revises: 2a5d7bb9efac
Create Date: 2025-06-29 09:34:44.889225

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2390504a64b4"
down_revision: Union[str, None] = "2a5d7bb9efac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "chatsession", sa.Column("socketio_room_id", sa.String(100), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("chatsession", "socketio_room_id")
