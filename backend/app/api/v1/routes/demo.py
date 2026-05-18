from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.demo import DemoClearResult, DemoSeedResult
from app.services.demo_service import DemoService

router = APIRouter()


@router.post("/seed", response_model=DemoSeedResult, status_code=status.HTTP_201_CREATED)
def seed_demo_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return DemoService(db).seed_for_user(current_user)


@router.delete("/seed", response_model=DemoClearResult)
def clear_demo_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return DemoService(db).clear_for_user(current_user)
