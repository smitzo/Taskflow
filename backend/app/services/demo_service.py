from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.task import TaskPriority, TaskStatus
from app.models.user import User
from app.models.workspace_member import WorkspaceRole
from app.repositories.task_repository import TaskRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.demo import DemoClearResult, DemoSeedResult
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

        existing_tasks, _total_existing = self.tasks.list_for_workspace(
            workspace_id=workspace.id,
            status=None,
            priority=None,
            assignee_id=None,
            page=1,
            size=100,
        )
        tasks_created = 0
        existing_titles = {task.title for task in existing_tasks}
        tasks_created = self._create_demo_tasks(workspace.id, current_user.id, existing_titles)

        self.db.commit()
        self.cache.delete(f"workspace:{workspace.id}:detail", f"workspace:{workspace.id}:task_summary")
        return DemoSeedResult(
            workspace_id=workspace.id,
            workspace_created=workspace_created,
            tasks_created=tasks_created,
            message="Demo data is ready.",
        )

    def clear_for_user(self, current_user: User) -> DemoClearResult:
        workspace = next(
            (item for item in self.workspaces.list_for_user(current_user.id) if item.name == "TaskFlow Demo"),
            None,
        )
        if workspace is None:
            return DemoClearResult(workspace_removed=False, message="No demo workspace found.")

        membership = self.workspaces.get_membership(workspace.id, current_user.id)
        if membership is None or membership.role != WorkspaceRole.OWNER:
            return DemoClearResult(workspace_removed=False, message="Only the demo workspace owner can remove demo data.")

        workspace_id = workspace.id
        self.db.delete(workspace)
        self.db.commit()
        self.cache.delete(f"workspace:{workspace_id}:detail", f"workspace:{workspace_id}:task_summary")
        return DemoClearResult(workspace_removed=True, message="Demo data removed.")

    def _create_demo_tasks(self, workspace_id: str, user_id: str, existing_titles: set[str]) -> int:
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
                "title": "Create demo data shortcut",
                "description": "Seed a usable workspace so reviewers can try the product without manual setup.",
                "priority": TaskPriority.HIGH,
                "status": TaskStatus.TODO,
                "deadline": now + timedelta(hours=18),
                "comment": "This should create tasks, comments, and useful status distribution.",
            },
            {
                "title": "Add auth rate limiting",
                "description": "Protect register, login, and refresh endpoints from rapid repeated attempts.",
                "priority": TaskPriority.CRITICAL,
                "status": TaskStatus.IN_PROGRESS,
                "deadline": now + timedelta(hours=12),
                "comment": "Use Redis in deployed environments with a memory fallback for local development.",
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
                "title": "Add activity log history",
                "description": "Record task status changes so users can explain how a task reached its current state.",
                "priority": TaskPriority.HIGH,
                "status": TaskStatus.REVIEW,
                "deadline": now + timedelta(days=3),
                "comment": "The activity endpoint should return actor and timestamps.",
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
                "title": "Prepare interviewer walkthrough",
                "description": "Use understanding.md as the source for architecture and security explanations.",
                "priority": TaskPriority.MEDIUM,
                "status": TaskStatus.DONE,
                "deadline": now + timedelta(days=2),
                "comment": "Focus on IDOR checks, service boundaries, and tradeoffs.",
            },
            {
                "title": "Validate owner-only workspace actions",
                "description": "Confirm non-owner members cannot rename workspaces or remove teammates.",
                "priority": TaskPriority.HIGH,
                "status": TaskStatus.IN_PROGRESS,
                "deadline": now + timedelta(days=2),
                "comment": "This maps directly to the assignment security requirements.",
            },
            {
                "title": "Smoke test frontend task creation",
                "description": "Create a task from the dashboard and verify it appears on the board.",
                "priority": TaskPriority.MEDIUM,
                "status": TaskStatus.TODO,
                "deadline": now + timedelta(hours=24),
                "comment": "Default deadline should be 24 hours from creation.",
            },
            {
                "title": "Document limitations",
                "description": "Call out local file storage, demo seed behavior, and future background jobs.",
                "priority": TaskPriority.LOW,
                "status": TaskStatus.REVIEW,
                "deadline": now + timedelta(days=6),
                "comment": "Honest limitations read better than pretending this is fully production deployed.",
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
            if sample["title"] in existing_titles:
                continue
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
            if sample["status"] != TaskStatus.TODO:
                self.tasks.add_activity_log(
                    task_id=task.id,
                    actor_id=user_id,
                    from_status=TaskStatus.TODO,
                    to_status=sample["status"],
                )
            self.tasks.add_comment(task_id=task.id, author_id=user_id, body=sample["comment"])
        return len([sample for sample in samples if sample["title"] not in existing_titles])
