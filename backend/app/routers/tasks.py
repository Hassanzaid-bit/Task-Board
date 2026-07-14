import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db import engine, get_conn
from ..deps import get_current_user
from ..domain import InvalidTransitionError, apply_status_change
from ..models import TaskIn, TaskOut, TaskUpdate
from ..realtime import manager
from ..schema import TASK_STATUSES, projects, tasks, users

router = APIRouter(prefix="/api/v1", tags=["tasks"])

# Reused by list/create/update so every response carries the assignee's name
# in one query — no per-task lookups (see ARCHITECTURE.md 5a on N+1s).
_task_with_assignee = (
    sa.select(tasks, users.c.display_name.label("assignee_name"))
    .select_from(tasks.outerjoin(users, tasks.c.assignee_id == users.c.id))
)


async def _ensure_assignee_exists(conn: AsyncConnection, user_id: int) -> None:
    exists = (await conn.execute(sa.select(users.c.id).where(users.c.id == user_id))).first()
    if exists is None:
        raise HTTPException(status_code=422, detail="Assignee does not exist")


async def _fetch_task(conn: AsyncConnection, task_id: int) -> dict:
    row = (
        await conn.execute(_task_with_assignee.where(tasks.c.id == task_id))
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return dict(row)


@router.get("/projects/{project_id}/tasks", response_model=list[TaskOut])
async def list_tasks(
    project_id: int,
    status: str | None = None,
    assignee_id: int | None = None,
    q: str | None = None,
    user: dict = Depends(get_current_user),
    conn: AsyncConnection = Depends(get_conn),
) -> list[TaskOut]:
    query = _task_with_assignee.where(tasks.c.project_id == project_id)
    if status is not None:
        if status not in TASK_STATUSES:
            raise HTTPException(status_code=422, detail=f"Unknown status {status!r}")
        query = query.where(tasks.c.status == status)
    if assignee_id is not None:
        query = query.where(tasks.c.assignee_id == assignee_id)
    if q:
        pattern = f"%{q}%"
        # Statuses are stored as e.g. "in_progress", but people type "in progress".
        status_pattern = f"%{q.strip().lower().replace(' ', '_')}%"
        query = query.where(
            sa.or_(
                tasks.c.title.ilike(pattern),
                tasks.c.description.ilike(pattern),
                users.c.display_name.ilike(pattern),
                tasks.c.status.like(status_pattern),
            )
        )
    rows = (await conn.execute(query.order_by(tasks.c.created_at))).mappings().all()
    return [TaskOut(**r) for r in rows]


@router.post("/projects/{project_id}/tasks", response_model=TaskOut, status_code=201)
async def create_task(
    project_id: int, body: TaskIn, user: dict = Depends(get_current_user)
) -> TaskOut:
    if body.status not in TASK_STATUSES:
        raise HTTPException(status_code=422, detail=f"Unknown status {body.status!r}")
    async with engine.begin() as conn:
        project_exists = (
            await conn.execute(sa.select(projects.c.id).where(projects.c.id == project_id))
        ).first()
        if project_exists is None:
            raise HTTPException(status_code=404, detail="Project not found")
        await _ensure_assignee_exists(conn, body.assignee_id)
        task_id = (
            await conn.execute(
                sa.insert(tasks)
                .values(project_id=project_id, **body.model_dump())
                .returning(tasks.c.id)
            )
        ).scalar_one()
        row = await _fetch_task(conn, task_id)
    # After commit — clients only ever hear about persisted state.
    await manager.broadcast(project_id, {"type": "task.created", "project_id": project_id})
    return TaskOut(**row)


@router.patch("/tasks/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: int, body: TaskUpdate, user: dict = Depends(get_current_user)
) -> TaskOut:
    changes = body.model_dump(exclude_unset=True)
    async with engine.begin() as conn:
        current = await _fetch_task(conn, task_id)

        if changes.get("assignee_id") is not None:
            await _ensure_assignee_exists(conn, changes["assignee_id"])

        if "status" in changes:
            try:
                status_updates = apply_status_change(
                    current_status=current["status"],
                    current_assignee_id=current["assignee_id"],
                    new_status=changes["status"],
                    actor_id=user["id"],
                )
            except InvalidTransitionError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            changes.pop("status")
            # Explicit assignee in the same request wins over auto-assign.
            changes = {**status_updates, **changes}

        if changes:
            await conn.execute(
                sa.update(tasks)
                .where(tasks.c.id == task_id)
                .values(**changes, updated_at=sa.func.now())
            )
        row = await _fetch_task(conn, task_id)
    await manager.broadcast(
        row["project_id"], {"type": "task.updated", "project_id": row["project_id"]}
    )
    return TaskOut(**row)


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: int, user: dict = Depends(get_current_user)) -> None:
    async with engine.begin() as conn:
        row = (
            await conn.execute(
                sa.delete(tasks).where(tasks.c.id == task_id).returning(tasks.c.project_id)
            )
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Task not found")
        project_id = row[0]
    await manager.broadcast(project_id, {"type": "task.deleted", "project_id": project_id})
