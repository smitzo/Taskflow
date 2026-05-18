from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.attachment import Attachment
from app.models.comment import Comment
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.task_activity import TaskActivityLog
from app.models.workspace_member import WorkspaceMember


class TaskRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        workspace_id: str,
        creator_id: str,
        assignee_id: str | None,
        title: str,
        description: str | None,
        priority: TaskPriority,
        deadline,
    ) -> Task:
        task = Task(
            workspace_id=workspace_id,
            creator_id=creator_id,
            assignee_id=assignee_id,
            title=title,
            description=description,
            priority=priority,
            deadline=deadline,
        )
        self.db.add(task)
        self.db.flush()
        return task

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        status: TaskStatus | None,
        priority: TaskPriority | None,
        assignee_id: str | None,
        page: int,
        size: int,
    ) -> tuple[list[Task], int]:
        statement: Select[tuple[Task]] = select(Task).where(Task.workspace_id == workspace_id, Task.is_deleted.is_(False))
        if status is not None:
            statement = statement.where(Task.status == status)
        if priority is not None:
            statement = statement.where(Task.priority == priority)
        if assignee_id is not None:
            statement = statement.where(Task.assignee_id == assignee_id)

        total = self.db.scalar(select(func.count()).select_from(statement.subquery())) or 0
        items = list(
            self.db.execute(
                statement.order_by(Task.created_at.desc()).offset((page - 1) * size).limit(size)
            )
            .scalars()
            .all()
        )
        return items, total

    def get_accessible_by_id(self, task_id: str, user_id: str, include_deleted: bool = False) -> Task | None:
        statement = (
            select(Task)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Task.workspace_id)
            .options(
                selectinload(Task.attachments),
                selectinload(Task.comments).selectinload(Comment.author),
                selectinload(Task.activity_logs).selectinload(TaskActivityLog.actor),
            )
            .where(Task.id == task_id, WorkspaceMember.user_id == user_id)
        )
        if not include_deleted:
            statement = statement.where(Task.is_deleted.is_(False))
        return self.db.execute(statement).scalar_one_or_none()

    def add_attachment(
        self,
        *,
        task_id: str,
        uploaded_by_id: str,
        original_filename: str,
        stored_filename: str,
        content_type: str | None,
        size_bytes: int,
    ) -> Attachment:
        attachment = Attachment(
            task_id=task_id,
            uploaded_by_id=uploaded_by_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            content_type=content_type,
            size_bytes=size_bytes,
        )
        self.db.add(attachment)
        self.db.flush()
        return attachment

    def get_attachment_accessible_by_id(self, attachment_id: str, user_id: str) -> Attachment | None:
        statement = (
            select(Attachment)
            .join(Task, Task.id == Attachment.task_id)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Task.workspace_id)
            .where(Attachment.id == attachment_id, WorkspaceMember.user_id == user_id, Task.is_deleted.is_(False))
        )
        return self.db.execute(statement).scalar_one_or_none()

    def add_comment(self, *, task_id: str, author_id: str, body: str) -> Comment:
        comment = Comment(task_id=task_id, author_id=author_id, body=body)
        self.db.add(comment)
        self.db.flush()
        return comment

    def list_comments(self, *, task_id: str, page: int, size: int) -> tuple[list[Comment], int]:
        statement = select(Comment).options(selectinload(Comment.author)).where(Comment.task_id == task_id)
        total = self.db.scalar(select(func.count()).select_from(statement.subquery())) or 0
        items = list(
            self.db.execute(
                statement.order_by(Comment.created_at.desc()).offset((page - 1) * size).limit(size)
            )
            .scalars()
            .all()
        )
        return items, total

    def add_activity_log(
        self,
        *,
        task_id: str,
        actor_id: str,
        from_status: TaskStatus | None,
        to_status: TaskStatus,
    ) -> TaskActivityLog:
        log = TaskActivityLog(
            task_id=task_id,
            actor_id=actor_id,
            from_status=from_status,
            to_status=to_status,
        )
        self.db.add(log)
        self.db.flush()
        return log

    def list_activity_logs(self, *, task_id: str, page: int, size: int) -> tuple[list[TaskActivityLog], int]:
        statement = select(TaskActivityLog).options(selectinload(TaskActivityLog.actor)).where(TaskActivityLog.task_id == task_id)
        total = self.db.scalar(select(func.count()).select_from(statement.subquery())) or 0
        items = list(
            self.db.execute(
                statement.order_by(TaskActivityLog.created_at.desc()).offset((page - 1) * size).limit(size)
            )
            .scalars()
            .all()
        )
        return items, total

    def summarize_workspace(self, workspace_id: str) -> dict:
        status_rows = self.db.execute(
            select(Task.status, func.count())
            .where(Task.workspace_id == workspace_id, Task.is_deleted.is_(False))
            .group_by(Task.status)
        ).all()
        priority_rows = self.db.execute(
            select(Task.priority, func.count())
            .where(Task.workspace_id == workspace_id, Task.is_deleted.is_(False))
            .group_by(Task.priority)
        ).all()

        status_counts = {status.value: count for status, count in status_rows}
        priority_counts = {priority.value: count for priority, count in priority_rows}
        return {
            "total": sum(status_counts.values()),
            "todo": status_counts.get(TaskStatus.TODO.value, 0),
            "in_progress": status_counts.get(TaskStatus.IN_PROGRESS.value, 0),
            "review": status_counts.get(TaskStatus.REVIEW.value, 0),
            "done": status_counts.get(TaskStatus.DONE.value, 0),
            "by_priority": {priority.value: priority_counts.get(priority.value, 0) for priority in TaskPriority},
        }
