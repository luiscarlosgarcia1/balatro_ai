from __future__ import annotations

from datetime import datetime, timezone


def int_or_zero(value: object) -> int:
    return int_or_none(value) or 0


def int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.lstrip("-").isdigit():
        return int(value)
    return None


def string_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def parse_seen_at(state: dict[str, object], *, fallback_timestamp: float) -> datetime:
    seen_at_raw = state.get("seen_at")
    if isinstance(seen_at_raw, str):
        try:
            return datetime.fromisoformat(seen_at_raw)
        except ValueError:
            pass

    return datetime.fromtimestamp(fallback_timestamp, tz=timezone.utc)
