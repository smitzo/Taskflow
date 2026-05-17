from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.attachment import Attachment
from app.models.comment import Comment
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.user import User
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.common import PaginatedResponse
from app.schemas.task import CommentCreate, CommentRead, TaskCreate, TaskRead, TaskUpdate
from app.services.email_service import EmailService


class TaskService:
    allowed_transitions = {
        TaskStatus.TODO: TaskStatus.IN_PROGRESS,
        TaskStatus.IN_PROGRESS: TaskStatus.REVIEW,
        TaskStatus.REVIEW: TaskStatus.DONE,
    }

    def __init__(self, db: Session) -> None:
        self.db = db
        self.tasks = TaskRepository(db)
        self.workspaces = WorkspaceRepository(db)
        self.users = UserRepository(db)
        self.email = EmailService()

    def create(self, workspace_id: str, payload: TaskCreate, current_user: User) -> Task:
        self._require_workspace_member(workspace_id, current_user.id)
        self._validate_assignee(workspace_id, payload.assignee_id)
        task = self.tasks.create(
            workspace_id=workspace_id,
            creator_id=current_user.id,
            assignee_id=payload.assignee_id,
            title=payload.title,
            description=payload.description,
            priority=payload.priority,
            deadline=payload.deadline,
        )
        self.db.commit()
        self.db.refresh(task)
        self._send_assignment_email(task, payload.assignee_id, current_user)
        return task

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        current_user: User,
        status_filter: TaskStatus | None,
        priority: TaskPriority | None,
        assignee_id: str | None,
        page: int,
        size: int,
    ) -> PaginatedResponse[TaskRead]:
        self._require_workspace_member(workspace_id, current_user.id)
        if assignee_id is not None:
            self._validate_assignee(workspace_id, assignee_id)
        items, total = self.tasks.list_for_workspace(
            workspace_id=workspace_id,
            status=status_filter,
            priority=priority,
            assignee_id=assignee_id,
            page=page,
            size=size,
        )
        return PaginatedResponse[TaskRead](items=items, page=page, size=size, total=total)

    def get_detail(self, task_id: str, current_user: User) -> Task:
        return self._require_task_access(task_id, current_user.id)

    def update(self, task_id: str, payload: TaskUpdate, current_user: User) -> Task:
        task = self._require_task_access(task_id, current_user.id)
        previous_assignee_id = task.assignee_id

        if payload.title is not None:
            task.title = payload.title
        if payload.description is not None:
            task.description = payload.description
        if payload.priority is not None:
            task.priority = payload.priority
        if payload.deadline is not None:
            task.deadline = payload.deadline
        if payload.assignee_id is not None:
            self._validate_assignee(task.workspace_id, payload.assignee_id)
            task.assignee_id = payload.assignee_id

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        if payload.assignee_id is not None and payload.assignee_id != previous_assignee_id:
            self._send_assignment_email(task, payload.assignee_id, current_user)
        return task

    def change_status(self, task_id: str, next_status: TaskStatus, current_user: User) -> Task:
        task = self._require_task_access(task_id, current_user.id)
        if task.status == next_status:
            return task
        expected_next = self.allowed_transitions.get(task.status)
        if expected_next != next_status:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status transition from {task.status.value} to {next_status.value}",
            )
        task.status = next_status
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def soft_delete(self, task_id: str, current_user: User) -> None:
        task = self._require_task_access(task_id, current_user.id)
        task.is_deleted = True
        self.db.add(task)
        self.db.commit()

    def attach_file(self, task_id: str, file: UploadFile, current_user: User) -> Attachment:
        task = self._require_task_access(task_id, current_user.id)
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)

        suffix = Path(file.filename or "upload").suffix
        stored_filename = f"{uuid4()}{suffix}"
        destination = upload_dir / stored_filename
        contents = file.file.read()
        destination.write_bytes(contents)

        attachment = self.tasks.add_attachment(
            task_id=task.id,
            uploaded_by_id=current_user.id,
            original_filename=file.filename or stored_filename,
            stored_filename=stored_filename,
            content_type=file.content_type,
            size_bytes=len(contents),
        )
        self.db.commit()
        self.db.refresh(attachment)
        return attachment

    def get_attachment_file(self, attachment_id: str, current_user: User) -> tuple[Attachment, Path]:
        attachment = self.tasks.get_attachment_accessible_by_id(attachment_id, current_user.id)
        if attachment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
        path = Path(settings.upload_dir) / attachment.stored_filename
        if not path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment file missing")
        return attachment, path

    def add_comment(self, task_id: str, payload: CommentCreate, current_user: User) -> Comment:
        task = self._require_task_access(task_id, current_user.id)
        comment = self.tasks.add_comment(task_id=task.id, author_id=current_user.id, body=payload.body)
        self.db.commit()
        self.db.refresh(comment)
        return comment

    def list_comments(self, task_id: str, current_user: User, page: int, size: int) -> PaginatedResponse[CommentRead]:
        task = self._require_task_access(task_id, current_user.id)
        items, total = self.tasks.list_comments(task_id=task.id, page=page, size=size)
        return PaginatedResponse[CommentRead](items=items, page=page, size=size, total=total)

    def _require_workspace_member(self, workspace_id: str, user_id: str) -> None:
        if self.workspaces.get_membership(workspace_id, user_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    def _require_task_access(self, task_id: str, user_id: str) -> Task:
        task = self.tasks.get_accessible_by_id(task_id, user_id)
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return task

    def _validate_assignee(self, workspace_id: str, assignee_id: str | None) -> None:
        if assignee_id is None:
            return
        if self.users.get_by_id(assignee_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee not found")
        if self.workspaces.get_membership(workspace_id, assignee_id) is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assignee must be a workspace member")

    def _send_assignment_email(self, task: Task, assignee_id: str | None, actor: User) -> None:
        if assignee_id is None:
            return
        assignee = self.users.get_by_id(assignee_id)
        if assignee is None:
            return
        self.email.send_email(
            to_email=assignee.email,
            subject=f"You were assigned: {task.title}",
            body=f"{actor.full_name} assigned you the TaskFlow task '{task.title}'.",
        )

