"""Time helpers and document serializers."""
from datetime import datetime, timezone
from typing import Optional


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def parse_iso(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _duration_ms(start, end) -> Optional[float]:
    a = parse_iso(start)
    b = parse_iso(end)
    if a is None or b is None:
        return None
    return (b - a).total_seconds() * 1000.0


def _avg_minutes(values_ms) -> float:
    values = [v for v in values_ms if v is not None and v >= 0]
    if not values:
        return 0.0
    return round(sum(values) / len(values) / 60000.0, 1)


def serialize_datetimes(doc: dict, keys: tuple) -> dict:
    doc = {k: v for k, v in doc.items() if k != "_id"}
    for k in keys:
        if k in doc and isinstance(doc[k], datetime):
            doc[k] = iso(doc[k])
    return doc
