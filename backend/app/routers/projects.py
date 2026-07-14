import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db import engine, get_conn
from ..deps import get_current_user
from ..models import ProjectIn, ProjectOut
from ..schema import projects, tasks

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    user: dict = Depends(get_current_user), conn: AsyncConnection = Depends(get_conn)
) -> list[ProjectOut]:
    task_count = (
        sa.select(sa.func.count())
        .where(tasks.c.project_id == projects.c.id)
        .scalar_subquery()
    )
    rows = (
        await conn.execute(
            sa.select(projects, task_count.label("task_count")).order_by(projects.c.created_at)
        )
    ).mappings().all()
    return [ProjectOut(**r) for r in rows]


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: int,
    user: dict = Depends(get_current_user),
    conn: AsyncConnection = Depends(get_conn),
) -> ProjectOut:
    row = (
        await conn.execute(sa.select(projects).where(projects.c.id == project_id))
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Project not found")
    count = (
        await conn.execute(
            sa.select(sa.func.count()).where(tasks.c.project_id == project_id)
        )
    ).scalar_one()
    return ProjectOut(**row, task_count=count)


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(body: ProjectIn, user: dict = Depends(get_current_user)) -> ProjectOut:
    async with engine.begin() as conn:
        row = (
            await conn.execute(
                sa.insert(projects)
                .values(name=body.name, description=body.description, created_by=user["id"])
                .returning(projects)
            )
        ).mappings().one()
    return ProjectOut(**row)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: int, body: ProjectIn, user: dict = Depends(get_current_user)
) -> ProjectOut:
    async with engine.begin() as conn:
        row = (
            await conn.execute(
                sa.update(projects)
                .where(projects.c.id == project_id)
                .values(name=body.name, description=body.description)
                .returning(projects)
            )
        ).mappings().first()
        if row is None:
            raise HTTPException(status_code=404, detail="Project not found")
    return ProjectOut(**row)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: int, user: dict = Depends(get_current_user)) -> None:
    async with engine.begin() as conn:
        result = await conn.execute(sa.delete(projects).where(projects.c.id == project_id))
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Project not found")
