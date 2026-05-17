from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_db

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, object]:
    database_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database_status = "unavailable"

    redis_status = "not_checked"
    try:
        import redis

        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1)
        redis_status = "ok" if client.ping() else "unavailable"
    except ImportError:
        redis_status = "client_missing"
    except Exception:
        redis_status = "unavailable"

    overall = "ok" if database_status == "ok" else "degraded"
    return {"status": overall, "checks": {"database": database_status, "redis": redis_status}}

