from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.task import TaskPriority, TaskStatus
from app.models.user import User
from app.repositories.task_repository import TaskRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.demo import DemoSeedResult
from app.services.cache_service import CacheService


class DemoService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.workspaces = WorkspaceRepository(db)
        self.tasks = TaskRepository(db)
        self.cache = CacheService()

    def seed_for_user(self, current_user: User) -> DemoSeedResult:
        workspace_created = False
        workspace = next(
            (item for item in self.workspaces.list_for_user(current_user.id) if item.name == "TaskFlow Demo"),
            None,
        )
        if workspace is None:
            workspace = self.workspaces.create(
                name="TaskFlow Demo",
                description="Demo workspace with sample tasks, comments, and workflow states.",
                owner_id=current_user.id,
            )
            workspace_created = True

        _existing_tasks, total_existing = self.tasks.list_for_workspace(
            workspace_id=workspace.id,
            status=None,
            priority=None,
            assignee_id=None,
            page=1,
            size=1,
        )
        tasks_created = 0
        if total_existing == 0:
            tasks_created = self._create_demo_tasks(workspace.id, current_user.id)

        self.db.commit()
        self.cache.delete(f"workspace:{workspace.id}:detail", f"workspace:{workspace.id}:task_summary")
        return DemoSeedResult(
            workspace_id=workspace.id,
            workspace_created=workspace_created,
            tasks_created=tasks_created,
            message="Demo data is ready.",
        )

    def _create_demo_tasks(self, workspace_id: str, user_id: str) -> int:
        now = datetime.now(timezone.utc)
        samples = [
            {
                "title": "Design workspace onboarding",
                "description": "Map the first-run flow and identify the minimum fields needed to invite teammates.",
                "priority": TaskPriority.HIGH,
                "status": TaskStatus.TODO,
                "deadline": now + timedelta(days=2),
                "comment": "Start with the API path and keep the UI lightweight.",
            },
            {
                "title": "Implement task filters",
                "description": "Verify status, priority, assignee, and pagination all work together.",
                "priority": TaskPriority.CRITICAL,
                "status": TaskStatus.IN_PROGRESS,
                "deadline": now + timedelta(days=1),
                "comment": "This is a good endpoint to show during review.",
            },
            {
                "title": "Review file upload flow",
                "description": "Attach a sample document and confirm access checks before download.",
                "priority": TaskPriority.MEDIUM,
                "status": TaskStatus.REVIEW,
                "deadline": now + timedelta(days=4),
                "comment": "Local disk storage is acceptable for the take-home scope.",
            },
            {
                "title": "Document tradeoffs",
                "description": "Keep README concise and move deeper interview explanations into understanding.md.",
                "priority": TaskPriority.LOW,
                "status": TaskStatus.DONE,
                "deadline": now + timedelta(days=5),
                "comment": "Done items prove the workflow summary and board counts.",
            },
        ]

        for sample in samples:
            task = self.tasks.create(
                workspace_id=workspace_id,
                creator_id=user_id,
                assignee_id=user_id,
                title=sample["title"],
                description=sample["description"],
                priority=sample["priority"],
                deadline=sample["deadline"],
            )
            task.status = sample["status"]
            self.db.add(task)
            self.db.flush()
            self.tasks.add_comment(task_id=task.id, author_id=user_id, body=sample["comment"])
        return len(samples)

