"""Data models for Helix's persistent memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
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


# ---------------------------------------------------------------------------
# Todo
# ---------------------------------------------------------------------------


class Priority(StrEnum):
    """Priority levels for todo items."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TodoStatus(StrEnum):
    """Lifecycle states for a todo item."""

    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class Todo:
    """A task/todo item for a user.

    Attributes:
        id: Firestore document ID (optional before saving).
        user_id: Telegram user ID that owns the todo.
        title: Short description of the task.
        description: Optional longer description.
        priority: Priority level (low, medium, high, urgent).
        due_date: Optional due date (date only).
        tags: Optional list of tags for categorisation.
        status: ``pending``, ``completed``, or ``cancelled``.
        created_at: UTC timestamp of creation.
        completed_at: UTC timestamp when completed (if applicable).
    """

    user_id: int
    title: str
    priority: Priority = Priority.MEDIUM
    description: str = ""
    due_date: date | None = None
    tags: list[str] = field(default_factory=list)
    status: TodoStatus = TodoStatus.PENDING
    id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary for Firestore."""
        return {
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "tags": self.tags,
            "status": self.status.value,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], doc_id: str) -> Todo:
        """Create a Todo from a Firestore document."""
        due_date_val = data.get("due_date")
        return cls(
            id=doc_id,
            user_id=data.get("user_id", 0),
            title=data.get("title", ""),
            description=data.get("description", ""),
            priority=Priority(data.get("priority", "medium")),
            due_date=date.fromisoformat(due_date_val) if due_date_val else None,
            tags=data.get("tags", []),
            status=TodoStatus(data.get("status", "pending")),
            created_at=data.get("created_at", datetime.now(UTC)),
            completed_at=data.get("completed_at"),
        )


# ---------------------------------------------------------------------------
# Expense
# ---------------------------------------------------------------------------


class ExpenseCategory(StrEnum):
    """Predefined expense categories."""

    FOOD = "food"
    TRANSPORT = "transport"
    HOUSING = "housing"
    UTILITIES = "utilities"
    ENTERTAINMENT = "entertainment"
    HEALTH = "health"
    EDUCATION = "education"
    SHOPPING = "shopping"
    SUBSCRIPTIONS = "subscriptions"
    OTHER = "other"


@dataclass
class Expense:
    """A tracked expense for a user.

    Attributes:
        id: Firestore document ID (optional before saving).
        user_id: Telegram user ID that owns the expense.
        amount: Expense amount (positive).
        currency: ISO 4217 currency code (default EUR).
        category: Expense category.
        description: Short note about the expense.
        expense_date: Date of the expense.
        tags: Optional list of tags.
        created_at: UTC timestamp of creation.
    """

    user_id: int
    amount: float
    category: ExpenseCategory
    description: str = ""
    currency: str = "EUR"
    expense_date: date = field(default_factory=lambda: datetime.now(UTC).date())
    tags: list[str] = field(default_factory=list)
    id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary for Firestore."""
        return {
            "user_id": self.user_id,
            "amount": self.amount,
            "currency": self.currency,
            "category": self.category.value,
            "description": self.description,
            "expense_date": self.expense_date.isoformat(),
            "tags": self.tags,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], doc_id: str) -> Expense:
        """Create an Expense from a Firestore document."""
        return cls(
            id=doc_id,
            user_id=data.get("user_id", 0),
            amount=float(data.get("amount", 0)),
            currency=data.get("currency", "EUR"),
            category=ExpenseCategory(data.get("category", "other")),
            description=data.get("description", ""),
            expense_date=date.fromisoformat(data["expense_date"])
            if data.get("expense_date")
            else datetime.now(UTC).date(),
            tags=data.get("tags", []),
            created_at=data.get("created_at", datetime.now(UTC)),
        )


# ---------------------------------------------------------------------------
# Habit
# ---------------------------------------------------------------------------


class HabitFrequency(StrEnum):
    """How often a habit should be performed."""

    DAILY = "daily"
    WEEKDAYS = "weekdays"
    WEEKLY = "weekly"


@dataclass
class Habit:
    """A tracked habit with streak information.

    Attributes:
        id: Firestore document ID (optional before saving).
        user_id: Telegram user ID that owns the habit.
        name: Habit name (e.g. "Exercise", "Read 30 min").
        frequency: Expected frequency (daily, weekdays, weekly).
        current_streak: Consecutive completions count.
        best_streak: All-time best streak.
        last_completed: Date of the most recent completion.
        active: Whether the habit is still being tracked.
        created_at: UTC timestamp of creation.
    """

    user_id: int
    name: str
    frequency: HabitFrequency = HabitFrequency.DAILY
    current_streak: int = 0
    best_streak: int = 0
    last_completed: date | None = None
    active: bool = True
    id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary for Firestore."""
        return {
            "user_id": self.user_id,
            "name": self.name,
            "frequency": self.frequency.value,
            "current_streak": self.current_streak,
            "best_streak": self.best_streak,
            "last_completed": self.last_completed.isoformat() if self.last_completed else None,
            "active": self.active,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], doc_id: str) -> Habit:
        """Create a Habit from a Firestore document."""
        last = data.get("last_completed")
        return cls(
            id=doc_id,
            user_id=data.get("user_id", 0),
            name=data.get("name", ""),
            frequency=HabitFrequency(data.get("frequency", "daily")),
            current_streak=data.get("current_streak", 0),
            best_streak=data.get("best_streak", 0),
            last_completed=date.fromisoformat(last) if last else None,
            active=data.get("active", True),
            created_at=data.get("created_at", datetime.now(UTC)),
        )

    def check_streak(self, today: date | None = None) -> bool:
        """Check whether the streak is still alive (not broken).

        A streak is alive if the last completion was within the expected
        frequency window relative to *today*.

        Returns:
            ``True`` if the streak is intact, ``False`` if broken.
        """
        if self.last_completed is None:
            return False
        today = today or datetime.now(UTC).date()
        gap = (today - self.last_completed).days

        if self.frequency == HabitFrequency.DAILY:
            return gap <= 1
        if self.frequency == HabitFrequency.WEEKDAYS:
            # Allow weekend gap (Fri->Mon = 3 days)
            return gap <= 3
        if self.frequency == HabitFrequency.WEEKLY:
            return gap <= 7
        return False


# ---------------------------------------------------------------------------
# Voice Note
# ---------------------------------------------------------------------------


@dataclass
class VoiceNote:
    """A saved voice-message transcription.

    Attributes:
        id: Firestore document ID (optional before saving).
        user_id: Telegram user ID that owns the note.
        text: Transcribed text content.
        duration_seconds: Length of the original audio.
        telegram_file_id: Telegram file_id for re-download.
        created_at: UTC timestamp of creation.
    """

    user_id: int
    text: str
    duration_seconds: int = 0
    telegram_file_id: str = ""
    id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary for Firestore."""
        return {
            "user_id": self.user_id,
            "text": self.text,
            "duration_seconds": self.duration_seconds,
            "telegram_file_id": self.telegram_file_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], doc_id: str) -> VoiceNote:
        """Create a VoiceNote from a Firestore document."""
        return cls(
            id=doc_id,
            user_id=data.get("user_id", 0),
            text=data.get("text", ""),
            duration_seconds=data.get("duration_seconds", 0),
            telegram_file_id=data.get("telegram_file_id", ""),
            created_at=data.get("created_at", datetime.now(UTC)),
        )


# ---------------------------------------------------------------------------
# Document & DocumentChunk
# ---------------------------------------------------------------------------


@dataclass
class Document:
    """Metadata for an uploaded document (PDF, DOCX, TXT).

    Attributes:
        id: Firestore document ID (optional before saving).
        user_id: Telegram user ID that owns the document.
        filename: Original filename.
        mime_type: MIME type of the uploaded file.
        page_count: Number of pages (0 for plain text).
        chunk_count: Number of text chunks created.
        created_at: UTC timestamp of creation.
    """

    user_id: int
    filename: str
    mime_type: str = ""
    page_count: int = 0
    chunk_count: int = 0
    id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary for Firestore."""
        return {
            "user_id": self.user_id,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "page_count": self.page_count,
            "chunk_count": self.chunk_count,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], doc_id: str) -> Document:
        """Create a Document from a Firestore document."""
        return cls(
            id=doc_id,
            user_id=data.get("user_id", 0),
            filename=data.get("filename", ""),
            mime_type=data.get("mime_type", ""),
            page_count=data.get("page_count", 0),
            chunk_count=data.get("chunk_count", 0),
            created_at=data.get("created_at", datetime.now(UTC)),
        )


@dataclass
class DocumentChunk:
    """A text chunk from a document, optionally with an embedding vector.

    Attributes:
        id: Firestore document ID (optional before saving).
        user_id: Telegram user ID that owns the chunk.
        document_id: Parent document Firestore ID.
        text: The chunk text content.
        chunk_index: Position of the chunk within the document.
        embedding: Optional float-vector embedding.
    """

    user_id: int
    document_id: str
    text: str
    chunk_index: int = 0
    embedding: list[float] | None = None
    id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary for Firestore."""
        return {
            "user_id": self.user_id,
            "document_id": self.document_id,
            "text": self.text,
            "chunk_index": self.chunk_index,
            "embedding": self.embedding,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], doc_id: str) -> DocumentChunk:
        """Create a DocumentChunk from a Firestore document."""
        return cls(
            id=doc_id,
            user_id=data.get("user_id", 0),
            document_id=data.get("document_id", ""),
            text=data.get("text", ""),
            chunk_index=data.get("chunk_index", 0),
            embedding=data.get("embedding"),
        )


# ---------------------------------------------------------------------------
# Smart Routine
# ---------------------------------------------------------------------------


class ConditionType(StrEnum):
    """Condition types for smart routines."""

    HABIT_NOT_LOGGED_BY = "habit_not_logged_by"
    NO_TODO_COMPLETED_TODAY = "no_todo_completed_today"
    DAILY_BRIEFING = "daily_briefing"
    CUSTOM_REMINDER = "custom_reminder"


@dataclass
class Routine:
    """A conditional automation that fires based on user-defined rules.

    Attributes:
        id: Firestore document ID (optional before saving).
        user_id: Telegram user ID that owns the routine.
        name: Human-readable routine name.
        condition_type: The type of condition that triggers this routine.
        condition_params: Type-specific parameters (check_time, habit_id, …).
        action_message: Message to send when the condition is met.
        active: Whether the routine is currently enabled.
        last_triggered: UTC datetime of the last successful trigger.
        created_at: UTC timestamp of creation.
    """

    user_id: int
    name: str
    condition_type: ConditionType
    condition_params: dict[str, Any] = field(default_factory=dict)
    action_message: str = ""
    active: bool = True
    last_triggered: datetime | None = None
    id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary for Firestore."""
        return {
            "user_id": self.user_id,
            "name": self.name,
            "condition_type": self.condition_type.value,
            "condition_params": self.condition_params,
            "action_message": self.action_message,
            "active": self.active,
            "last_triggered": self.last_triggered,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], doc_id: str) -> Routine:
        """Create a Routine from a Firestore document."""
        return cls(
            id=doc_id,
            user_id=data.get("user_id", 0),
            name=data.get("name", ""),
            condition_type=ConditionType(data.get("condition_type", "custom_reminder")),
            condition_params=data.get("condition_params", {}),
            action_message=data.get("action_message", ""),
            active=data.get("active", True),
            last_triggered=data.get("last_triggered"),
            created_at=data.get("created_at", datetime.now(UTC)),
        )
