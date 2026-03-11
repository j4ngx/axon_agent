"""Data models for Helix's persistent memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any


@dataclass
class Message:
    """A single message in a conversation.

    Attributes:
        id: Firestore document ID (optional before saving).
        user_id: Telegram user ID that owns the conversation.
        role: Message role — ``user``, ``assistant``, ``system``, or ``tool``.
        content: The message text.
        timestamp: UTC timestamp of the message.
    """

    user_id: int
    role: str
    content: str
    id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary for Firestore."""
        return {
            "user_id": self.user_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], doc_id: str) -> Message:
        """Create a Message from a Firestore document data."""
        return cls(
            id=doc_id,
            user_id=data.get("user_id", 0),
            role=data.get("role", ""),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", datetime.now(UTC)),
        )


class Recurrence(StrEnum):
    """Supported recurrence patterns for reminders."""

    DAILY = "daily"
    WEEKDAYS = "weekdays"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class Reminder:
    """A scheduled reminder for a user.

    Attributes:
        id: Firestore document ID (optional before saving).
        user_id: Telegram user ID that owns the reminder.
        message: The text to send when the reminder fires.
        trigger_at: UTC datetime when the reminder should fire next.
        recurrence: Optional recurrence pattern (``None`` = one-time).
        status: ``pending`` or ``completed``.
        created_at: UTC timestamp of creation.
    """

    user_id: int
    message: str
    trigger_at: datetime
    recurrence: Recurrence | None = None
    status: str = "pending"
    id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary for Firestore."""
        return {
            "user_id": self.user_id,
            "message": self.message,
            "trigger_at": self.trigger_at,
            "recurrence": self.recurrence.value if self.recurrence else None,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], doc_id: str) -> Reminder:
        """Create a Reminder from a Firestore document."""
        recurrence_val = data.get("recurrence")
        return cls(
            id=doc_id,
            user_id=data.get("user_id", 0),
            message=data.get("message", ""),
            trigger_at=data.get("trigger_at", datetime.now(UTC)),
            recurrence=Recurrence(recurrence_val) if recurrence_val else None,
            status=data.get("status", "pending"),
            created_at=data.get("created_at", datetime.now(UTC)),
        )

    def compute_next_trigger(self) -> datetime | None:
        """Compute the next trigger time based on recurrence.

        Returns:
            The next trigger datetime, or ``None`` if one-time.
        """
        if self.recurrence is None:
            return None

        base = self.trigger_at
        if self.recurrence == Recurrence.DAILY:
            return base + timedelta(days=1)

        if self.recurrence == Recurrence.WEEKDAYS:
            next_day = base + timedelta(days=1)
            # Skip Saturday (5) and Sunday (6)
            while next_day.weekday() >= 5:
                next_day += timedelta(days=1)
            return next_day

        if self.recurrence == Recurrence.WEEKLY:
            return base + timedelta(weeks=1)

        if self.recurrence == Recurrence.MONTHLY:
            # Move to same day next month
            month = base.month % 12 + 1
            year = base.year + (1 if base.month == 12 else 0)
            day = min(base.day, 28)  # safe cap for all months
            return base.replace(year=year, month=month, day=day)

        return None
