"""Unit tests for the status-transition business rules (pure logic, no I/O)."""

import pytest

from app.domain import InvalidTransitionError, apply_status_change


def test_unknown_status_is_rejected():
    with pytest.raises(InvalidTransitionError):
        apply_status_change(
            current_status="todo", current_assignee_id=None, new_status="archived", actor_id=1
        )


def test_same_status_is_a_noop():
    updates = apply_status_change(
        current_status="in_progress", current_assignee_id=7, new_status="in_progress", actor_id=1
    )
    assert updates == {}


def test_moving_unassigned_task_to_in_progress_assigns_the_mover():
    updates = apply_status_change(
        current_status="todo", current_assignee_id=None, new_status="in_progress", actor_id=42
    )
    assert updates == {"status": "in_progress", "assignee_id": 42}


def test_existing_assignee_is_kept_on_transition():
    updates = apply_status_change(
        current_status="todo", current_assignee_id=7, new_status="in_progress", actor_id=42
    )
    assert updates == {"status": "in_progress"}


def test_reopening_a_done_task_is_allowed():
    updates = apply_status_change(
        current_status="done", current_assignee_id=7, new_status="todo", actor_id=7
    )
    assert updates == {"status": "todo"}
