"""Pydantic request/response models for the /api/v1 surface."""

from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, model_validator

# --- Auth ---

class RegisterIn(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- Projects ---

class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)


class ProjectOut(BaseModel):
    id: int
    name: str
    description: str
    created_by: int | None
    created_at: datetime
    task_count: int = 0


# --- Tasks ---

class TaskIn(BaseModel):
    """Title, description, assignee, and due date are mandatory on every task."""

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    status: str = "todo"
    assignee_id: int
    due_date: date


class TaskUpdate(BaseModel):
    """PATCH semantics: only provided fields are changed.

    Required fields (title, description, assignee, due date) may be
    replaced but never cleared.
    """

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=5000)
    status: str | None = None
    assignee_id: int | None = None
    due_date: date | None = None

    @model_validator(mode="after")
    def _reject_clearing_required_fields(self):
        for field in ("title", "description", "assignee_id", "due_date"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} is required and cannot be cleared")
        return self


class TaskOut(BaseModel):
    id: int
    project_id: int
    title: str
    description: str
    status: str
    assignee_id: int | None
    assignee_name: str | None
    due_date: date | None
    created_at: datetime
    updated_at: datetime
