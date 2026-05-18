"""add task activity logs

Revision ID: 20260518_0002
Revises: 20260516_0001
Create Date: 2026-05-18 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260518_0002"
down_revision = "20260516_0001"
branch_labels = None
depends_on = None

task_status = postgresql.ENUM(
    "todo",
    "in_progress",
    "review",
    "done",
    name="taskstatus",
    create_type=False,
)


def upgrade() -> None:
    op.create_table(
        "task_activity_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("from_status", task_status, nullable=True),
        sa.Column("to_status", task_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_task_activity_logs_task_id", "task_activity_logs", ["task_id"])
    op.create_index("ix_task_activity_logs_actor_id", "task_activity_logs", ["actor_id"])


def downgrade() -> None:
    op.drop_index("ix_task_activity_logs_actor_id", table_name="task_activity_logs")
    op.drop_index("ix_task_activity_logs_task_id", table_name="task_activity_logs")
    op.drop_table("task_activity_logs")