"""SQLAlchemy declarative models for Axon's persistent memory."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, Index, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base for all Axon models."""


class Message(Base):
    """A single message in a conversation.

    Attributes:
        id: Auto-incrementing primary key.
        user_id: Telegram user ID that owns the conversation.
        role: Message role — ``user``, ``assistant``, ``system``, or ``tool``.
        content: The message text.
        timestamp: UTC timestamp of the message.
    """

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (Index("ix_messages_user_id_timestamp", "user_id", "timestamp"),)

    def __repr__(self) -> str:
        return (
            f"Message(id={self.id!r}, user_id={self.user_id!r}, "
            f"role={self.role!r}, timestamp={self.timestamp!r})"
        )
