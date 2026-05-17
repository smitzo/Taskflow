from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember, WorkspaceRole
from app.repositories.user_repository import UserRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.workspace import WorkspaceCreate, WorkspaceMemberRead, WorkspaceUpdate
from app.services.email_service import EmailService


class WorkspaceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.workspaces = WorkspaceRepository(db)
        self.users = UserRepository(db)
        self.email = EmailService()

    def create(self, payload: WorkspaceCreate, current_user: User) -> Workspace:
        workspace = self.workspaces.create(payload.name, payload.description, current_user.id)
        self.db.commit()
        self.db.refresh(workspace)
        return workspace

    def list_for_user(self, current_user: User) -> list[Workspace]:
        return self.workspaces.list_for_user(current_user.id)

    def get_detail(self, workspace_id: str, current_user: User) -> Workspace:
        workspace = self.workspaces.get_detail_for_user(workspace_id, current_user.id)
        if workspace is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
        return workspace

    def update(self, workspace_id: str, payload: WorkspaceUpdate, current_user: User) -> Workspace:
        workspace, _membership = self._require_owner(workspace_id, current_user.id)
        if payload.name is not None:
            workspace.name = payload.name
        if payload.description is not None:
            workspace.description = payload.description
        self.db.add(workspace)
        self.db.commit()
        self.db.refresh(workspace)
        return workspace

    def invite_member(self, workspace_id: str, email: str, current_user: User) -> WorkspaceMemberRead:
        workspace, _membership = self._require_owner(workspace_id, current_user.id)
        invited_user = self.users.get_by_email(email)
        if invited_user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User must register before they can be invited")

        existing_membership = self.workspaces.get_membership(workspace_id, invited_user.id)
        if existing_membership is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a workspace member")

        try:
            membership = self.workspaces.add_member(workspace_id, invited_user.id)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a workspace member") from None

        self.db.refresh(membership)
        self.email.send_email(
            to_email=invited_user.email,
            subject=f"You were added to {workspace.name}",
            body=f"{current_user.full_name} added you to the TaskFlow workspace '{workspace.name}'.",
        )
        return WorkspaceMemberRead(user=invited_user, role=membership.role, joined_at=membership.created_at)

    def remove_member(self, workspace_id: str, user_id: str, current_user: User) -> None:
        self._require_owner(workspace_id, current_user.id)
        if user_id == current_user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Owners cannot remove themselves")
        membership = self.workspaces.get_membership(workspace_id, user_id)
        if membership is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace member not found")
        if membership.role == WorkspaceRole.OWNER:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove another owner")
        self.workspaces.remove_member(membership)
        self.db.commit()

    def require_member(self, workspace_id: str, user_id: str) -> WorkspaceMember:
        membership = self.workspaces.get_membership(workspace_id, user_id)
        if membership is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
        return membership

    def _require_owner(self, workspace_id: str, user_id: str) -> tuple[Workspace, WorkspaceMember]:
        workspace = self.workspaces.get_by_id(workspace_id)
        membership = self.workspaces.get_membership(workspace_id, user_id)
        if workspace is None or membership is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
        if membership.role != WorkspaceRole.OWNER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner role required")
        return workspace, membership

