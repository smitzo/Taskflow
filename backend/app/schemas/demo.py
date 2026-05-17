from pydantic import BaseModel


class DemoSeedResult(BaseModel):
    workspace_id: str
    workspace_created: bool
    tasks_created: int
    message: str

