"""Business-day helpers.

Timestamps are stored in UTC, but "bugun" means Tashkent's calendar day —
these two facts have to be reconciled in every daily/weekly count, so the
conversion lives in one place and both the admin API and the bot panel use it.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TASHKENT = ZoneInfo("Asia/Tashkent")
UTC = ZoneInfo("UTC")


def today_local() -> date:
    return datetime.now(TASHKENT).date()


def day_start_utc(days_ago: int = 0) -> datetime:
    """UTC instant that Tashkent's calendar day started, `days_ago` days back."""
    local_midnight = datetime.combine(
        today_local() - timedelta(days=days_ago), datetime.min.time(), tzinfo=TASHKENT
    )
    return local_midnight.astimezone(UTC).replace(tzinfo=None)


def to_local(dt: datetime | None) -> datetime | None:
    """Naive-UTC timestamp from the database -> aware Tashkent time."""
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC).astimezone(TASHKENT)
