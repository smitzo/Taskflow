from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.workspace_member import WorkspaceRole
from app.schemas.user import UserRead


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class WorkspaceMemberInvite(BaseModel):
    email: EmailStr


class WorkspaceMemberRead(BaseModel):
    user: UserRead
    role: WorkspaceRole
    joined_at: datetime


class WorkspaceRead(BaseModel):
    id: str
    name: str
    description: str | None
    created_by_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkspaceDetail(WorkspaceRead):
    members: list[WorkspaceMemberRead]

