from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.task import TaskPriority, TaskStatus
from app.schemas.user import UserRead


class AttachmentRead(BaseModel):
    id: str
    original_filename: str
    content_type: str | None
    size_bytes: int
    uploaded_by_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class CommentRead(BaseModel):
    id: str
    task_id: str
    author_id: str
    author: UserRead
    body: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskCreate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=5000)
    assignee_id: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    deadline: datetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=5000)
    assignee_id: str | None = None
    priority: TaskPriority | None = None
    deadline: datetime | None = None


class TaskStatusUpdate(BaseModel):
    status: TaskStatus


class TaskRead(BaseModel):
    id: str
    workspace_id: str
    creator_id: str
    assignee_id: str | None
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    deadline: datetime | None
    is_deleted: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskDetail(TaskRead):
    attachments: list[AttachmentRead]
    comments: list[CommentRead]


class TaskActivityLogRead(BaseModel):
    id: str
    task_id: str
    actor_id: str
    actor: UserRead
    from_status: TaskStatus | None
    to_status: TaskStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskSummary(BaseModel):
    total: int
    todo: int
    in_progress: int
    review: int
    done: int
    by_priority: dict[str, int]
