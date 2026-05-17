from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember, WorkspaceRole


class WorkspaceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, name: str, description: str | None, owner_id: str) -> Workspace:
        workspace = Workspace(name=name, description=description, created_by_id=owner_id)
        self.db.add(workspace)
        self.db.flush()
        owner_membership = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=owner_id,
            role=WorkspaceRole.OWNER,
        )
        self.db.add(owner_membership)
        self.db.flush()
        return workspace

    def list_for_user(self, user_id: str) -> list[Workspace]:
        statement = (
            select(Workspace)
            .join(WorkspaceMember)
            .where(WorkspaceMember.user_id == user_id)
            .order_by(Workspace.created_at.desc())
        )
        return list(self.db.execute(statement).scalars().all())

    def get_by_id(self, workspace_id: str) -> Workspace | None:
        return self.db.get(Workspace, workspace_id)

    def get_detail_for_user(self, workspace_id: str, user_id: str) -> Workspace | None:
        statement = (
            select(Workspace)
            .join(WorkspaceMember)
            .options(selectinload(Workspace.members).selectinload(WorkspaceMember.user))
            .where(Workspace.id == workspace_id, WorkspaceMember.user_id == user_id)
        )
        return self.db.execute(statement).scalar_one_or_none()

    def get_membership(self, workspace_id: str, user_id: str) -> WorkspaceMember | None:
        statement = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        return self.db.execute(statement).scalar_one_or_none()

    def add_member(self, workspace_id: str, user_id: str, role: WorkspaceRole = WorkspaceRole.MEMBER) -> WorkspaceMember:
        membership = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=role)
        self.db.add(membership)
        self.db.flush()
        return membership

    def remove_member(self, membership: WorkspaceMember) -> None:
        self.db.delete(membership)

