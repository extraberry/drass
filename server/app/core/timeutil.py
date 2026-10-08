from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC timestamp (stored as UTC everywhere)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
