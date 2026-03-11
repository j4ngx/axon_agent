"""Tests for the ``Reminder`` model and ``Recurrence`` enum."""

from __future__ import annotations

from datetime import UTC, datetime

from helix.memory.models import Recurrence, Reminder


class TestReminder:
    """Unit tests for ``Reminder`` dataclass."""

    def test_when_to_dict_expect_all_fields(self) -> None:
        r = Reminder(
            user_id=42,
            message="Test",
            trigger_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
            recurrence=Recurrence.DAILY,
        )
        d = r.to_dict()
        assert d["user_id"] == 42
        assert d["message"] == "Test"
        assert d["recurrence"] == "daily"
        assert d["status"] == "pending"

    def test_when_from_dict_expect_reminder_reconstructed(self) -> None:
        data = {
            "user_id": 42,
            "message": "Test",
            "trigger_at": datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
            "recurrence": "weekly",
            "status": "pending",
            "created_at": datetime(2026, 5, 1, tzinfo=UTC),
        }
        r = Reminder.from_dict(data, "doc1")
        assert r.id == "doc1"
        assert r.recurrence == Recurrence.WEEKLY

    def test_when_from_dict_without_recurrence_expect_none(self) -> None:
        data = {
            "user_id": 42,
            "message": "Test",
            "trigger_at": datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
            "recurrence": None,
            "status": "pending",
            "created_at": datetime(2026, 5, 1, tzinfo=UTC),
        }
        r = Reminder.from_dict(data, "doc2")
        assert r.recurrence is None


class TestComputeNextTrigger:
    """Unit tests for ``Reminder.compute_next_trigger()``."""

    def test_when_one_time_expect_none(self) -> None:
        r = Reminder(
            user_id=42,
            message="Once",
            trigger_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
            recurrence=None,
        )
        assert r.compute_next_trigger() is None

    def test_when_daily_expect_plus_one_day(self) -> None:
        r = Reminder(
            user_id=42,
            message="Daily",
            trigger_at=datetime(2026, 6, 1, 9, 0, tzinfo=UTC),
            recurrence=Recurrence.DAILY,
        )
        assert r.compute_next_trigger() == datetime(2026, 6, 2, 9, 0, tzinfo=UTC)

    def test_when_weekly_expect_plus_seven_days(self) -> None:
        r = Reminder(
            user_id=42,
            message="Weekly",
            trigger_at=datetime(2026, 6, 1, 9, 0, tzinfo=UTC),
            recurrence=Recurrence.WEEKLY,
        )
        assert r.compute_next_trigger() == datetime(2026, 6, 8, 9, 0, tzinfo=UTC)

    def test_when_monthly_expect_same_day_next_month(self) -> None:
        r = Reminder(
            user_id=42,
            message="Monthly",
            trigger_at=datetime(2026, 1, 15, 10, 0, tzinfo=UTC),
            recurrence=Recurrence.MONTHLY,
        )
        assert r.compute_next_trigger() == datetime(2026, 2, 15, 10, 0, tzinfo=UTC)

    def test_when_monthly_on_31st_expect_capped_to_28(self) -> None:
        r = Reminder(
            user_id=42,
            message="Monthly edge",
            trigger_at=datetime(2026, 1, 31, 10, 0, tzinfo=UTC),
            recurrence=Recurrence.MONTHLY,
        )
        assert r.compute_next_trigger() == datetime(2026, 2, 28, 10, 0, tzinfo=UTC)

    def test_when_weekdays_on_monday_expect_tuesday(self) -> None:
        # 2026-03-02 is a Monday
        r = Reminder(
            user_id=42,
            message="Weekdays",
            trigger_at=datetime(2026, 3, 2, 9, 0, tzinfo=UTC),
            recurrence=Recurrence.WEEKDAYS,
        )
        assert r.compute_next_trigger() == datetime(2026, 3, 3, 9, 0, tzinfo=UTC)

    def test_when_weekdays_on_friday_expect_monday(self) -> None:
        # 2026-03-06 is a Friday
        r = Reminder(
            user_id=42,
            message="Weekdays",
            trigger_at=datetime(2026, 3, 6, 9, 0, tzinfo=UTC),
            recurrence=Recurrence.WEEKDAYS,
        )
        assert r.compute_next_trigger() == datetime(2026, 3, 9, 9, 0, tzinfo=UTC)

    def test_when_monthly_in_december_expect_january_next_year(self) -> None:
        r = Reminder(
            user_id=42,
            message="Year wrap",
            trigger_at=datetime(2026, 12, 10, 10, 0, tzinfo=UTC),
            recurrence=Recurrence.MONTHLY,
        )
        assert r.compute_next_trigger() == datetime(2027, 1, 10, 10, 0, tzinfo=UTC)
