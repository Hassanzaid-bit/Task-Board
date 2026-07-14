"""Pure business rules for task status transitions — no I/O, unit-testable.

Rules:
- A status must be one of TASK_STATUSES.
- Moving an unassigned task to "in_progress" auto-assigns the user who
  moved it: work in progress should always have an owner.
- Any transition between valid statuses is allowed (including reopening
  a done task).
"""

from .schema import TASK_STATUSES


class InvalidTransitionError(ValueError):
    pass


def apply_status_change(
    *, current_status: str, current_assignee_id: int | None, new_status: str, actor_id: int
) -> dict:
    """Returns the column updates a status change implies.

    Raises InvalidTransitionError for unknown statuses.
    Returns {} when the change is a no-op.
    """
    if new_status not in TASK_STATUSES:
        raise InvalidTransitionError(
            f"Unknown status {new_status!r}; must be one of {', '.join(TASK_STATUSES)}"
        )

    if new_status == current_status:
        return {}

    updates: dict = {"status": new_status}
    if new_status == "in_progress" and current_assignee_id is None:
        updates["assignee_id"] = actor_id
    return updates
