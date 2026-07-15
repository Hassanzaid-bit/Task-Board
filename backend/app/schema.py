"""Explicit schema via SQLAlchemy Core — no ORM relationship mapping.

Every table and constraint is spelled out here so the data model is
inspectable in one place (see ARCHITECTURE.md §1).
"""

import sqlalchemy as sa

metadata = sa.MetaData()

TASK_STATUSES = ("todo", "in_progress", "done")


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


users = sa.Table(
    "users",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("email", sa.String(255), nullable=False, unique=True),
    sa.Column("display_name", sa.String(100), nullable=False),
    sa.Column("password_hash", sa.String(255), nullable=False),
    _created_at(),
)

projects = sa.Table(
    "projects",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("name", sa.String(200), nullable=False),
    sa.Column("description", sa.Text, nullable=False, server_default=""),
    sa.Column(
        "created_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    ),
    _created_at(),
)

tasks = sa.Table(
    "tasks",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column(
        "project_id",
        sa.Integer,
        sa.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("title", sa.String(200), nullable=False),
    sa.Column("description", sa.Text, nullable=False, server_default=""),
    sa.Column("status", sa.String(20), nullable=False, server_default="todo"),
    sa.Column(
        "assignee_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    ),
    sa.Column("due_date", sa.Date, nullable=True),
    _created_at(),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    ),
    sa.CheckConstraint(
        "status IN ('todo', 'in_progress', 'done')", name="ck_tasks_status_valid"
    ),
)
