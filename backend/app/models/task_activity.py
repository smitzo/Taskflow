from sqlalchemy import Enum as SQLEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, generate_uuid
from app.models.task import TaskStatus


class TaskActivityLog(TimestampMixin, Base):
    __tablename__ = "task_activity_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    from_status: Mapped[TaskStatus | None] = mapped_column(
        SQLEnum(TaskStatus, values_callable=lambda enum: [item.value for item in enum]),
        nullable=True,
    )
    to_status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(TaskStatus, values_callable=lambda enum: [item.value for item in enum]),
        nullable=False,
    )

    task = relationship("Task", back_populates="activity_logs")
    actor = relationship("User")
