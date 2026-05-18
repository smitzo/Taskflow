from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.models.task import TaskPriority, TaskStatus
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.task import (
    AttachmentRead,
    CommentCreate,
    CommentRead,
    TaskCreate,
    TaskActivityLogRead,
    TaskDetail,
    TaskRead,
    TaskStatusUpdate,
    TaskSummary,
    TaskUpdate,
)
from app.services.task_service import TaskService

router = APIRouter()


@router.post("/workspaces/{workspace_id}/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    workspace_id: str,
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TaskService(db).create(workspace_id, payload, current_user)


@router.get("/workspaces/{workspace_id}/tasks", response_model=PaginatedResponse[TaskRead])
def list_tasks(
    workspace_id: str,
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    priority: TaskPriority | None = None,
    assignee_id: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TaskService(db).list_for_workspace(
        workspace_id=workspace_id,
        current_user=current_user,
        status_filter=status_filter,
        priority=priority,
        assignee_id=assignee_id,
        page=page,
        size=size,
    )


@router.get("/workspaces/{workspace_id}/tasks/summary", response_model=TaskSummary)
def get_task_summary(
    workspace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TaskService(db).summarize_workspace(workspace_id, current_user)


@router.get("/tasks/{task_id}", response_model=TaskDetail)
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TaskService(db).get_detail(task_id, current_user)


@router.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(
    task_id: str,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TaskService(db).update(task_id, payload, current_user)


@router.patch("/tasks/{task_id}/status", response_model=TaskRead)
def change_task_status(
    task_id: str,
    payload: TaskStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TaskService(db).change_status(task_id, payload.status, current_user)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    TaskService(db).soft_delete(task_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/tasks/{task_id}/attachments", response_model=AttachmentRead, status_code=status.HTTP_201_CREATED)
def upload_attachment(
    task_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TaskService(db).attach_file(task_id, file, current_user)


@router.get("/attachments/{attachment_id}")
def download_attachment(
    attachment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attachment, path = TaskService(db).get_attachment_file(attachment_id, current_user)
    return FileResponse(path, media_type=attachment.content_type, filename=attachment.original_filename)


@router.post("/tasks/{task_id}/comments", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
def add_comment(
    task_id: str,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TaskService(db).add_comment(task_id, payload, current_user)


@router.get("/tasks/{task_id}/comments", response_model=PaginatedResponse[CommentRead])
def list_comments(
    task_id: str,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TaskService(db).list_comments(task_id, current_user, page, size)


@router.get("/tasks/{task_id}/activity", response_model=PaginatedResponse[TaskActivityLogRead])
def list_activity(
    task_id: str,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TaskService(db).list_activity(task_id, current_user, page, size)
