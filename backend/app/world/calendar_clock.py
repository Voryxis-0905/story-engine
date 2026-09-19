"""World-defined calendars and one deterministic clock for narrative time."""
from __future__ import annotations

import calendar as _calendar


def normalize_calendar(value: object) -> dict:
    """Accept a builder calendar or fall back to the old 30-day world calendar."""
    raw = value if isinstance(value, dict) else {}
    kind = "gregorian" if raw.get("kind") == "gregorian" else "custom"
    months = []
    if kind == "custom":
        for item in raw.get("months", []) if isinstance(raw.get("months"), list) else []:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                continue
            try:
                days = int(item.get("days", 30))
            except (TypeError, ValueError):
                continue
            if item["name"].strip() and 1 <= days <= 366:
                months.append({"name": item["name"].strip(), "days": days})
        if not months:
            months = [{"name": f"Month {i}", "days": 30} for i in range(1, 13)]
    seasons = []
    for item in raw.get("seasons", []) if isinstance(raw.get("seasons"), list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            continue
        indexes = item.get("months", [])
        if isinstance(indexes, list):
            valid = [n for n in indexes if isinstance(n, int) and not isinstance(n, bool)
                     and 1 <= n <= (12 if kind == "gregorian" else len(months))]
            if valid and item["name"].strip():
                seasons.append({"name": item["name"].strip(), "months": valid})
    if kind == "gregorian" and not seasons:
        seasons = [{"name": name, "months": numbers} for name, numbers in (
            ("Winter", [12, 1, 2]), ("Spring", [3, 4, 5]),
            ("Summer", [6, 7, 8]), ("Autumn", [9, 10, 11]),
        )]
    return {
        "kind": kind,
        "months": months,
        "seasons": seasons,
        "year_label": str(raw.get("year_label") or "Year")[:80],
        "era": str(raw.get("era") or "")[:80],
    }


def normalize_start_clock(value: object, calendar_config: object) -> dict:
    """Validate the date selected during world generation."""
    raw = value if isinstance(value, dict) else {}
    cal = normalize_calendar(calendar_config)
    def bounded(key: str, default: int, maximum: int) -> int:
        item = raw.get(key, default)
        try:
            return min(maximum, max(1, int(item)))
        except (TypeError, ValueError):
            return default
    year = bounded("year", 1, 999999)
    month = bounded("month", 1, 12 if cal["kind"] == "gregorian" else len(cal["months"]))
    day = bounded("day", 1, _month_days(cal, year, month))
    try:
        minute = min(1439, max(0, int(raw.get("minute_of_day", 480))))
    except (TypeError, ValueError):
        minute = 480
    hour = minute // 60
    clock = {"year": year, "month": month, "day": day,
             "minute_of_day": minute, "second_of_day": minute * 60,
             "elapsed_seconds": 0, "elapsed_minutes": 0, "tick": 0,
             "time_of_day": ("morning" if 5 <= hour < 12 else "afternoon" if hour < 17
                             else "evening" if hour < 22 else "night")}
    for season in cal["seasons"]:
        if month in season["months"]:
            clock["season"] = season["name"]
            break
    return clock


def normalize_elapsed_time(value: object, *, fallback_minutes: int = 5,
                           max_minutes: int | None = None) -> dict:
    """Reject malformed or implausible AI durations without changing the clock."""
    parts = {}
    valid = isinstance(value, dict)
    for unit in ("days", "hours", "minutes", "seconds"):
        raw = value.get(unit, 0) if valid else 0
        if not isinstance(raw, int) or isinstance(raw, bool) or raw < 0:
            valid = False
            break
        parts[unit] = raw
    seconds = (parts.get("days", 0) * 86400 + parts.get("hours", 0) * 3600
               + parts.get("minutes", 0) * 60 + parts.get("seconds", 0))
    limit = max_minutes * 60 if max_minutes is not None else None
    if not valid or seconds <= 0 or (limit is not None and seconds > limit):
        seconds = max(0, fallback_minutes) * 60
        source = "fallback"
    else:
        source = "model"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, rem = divmod(rem, 60)
    reason = value.get("reason", "") if isinstance(value, dict) and source == "model" else ""
    return {"days": days, "hours": hours, "minutes": minutes,
            "seconds": rem, "total_seconds": seconds, "source": source,
            "reason": str(reason)[:240]}


def _month_days(calendar: dict, year: int, month: int) -> int:
    if calendar["kind"] == "gregorian":
        return _calendar.monthrange(max(1, year), month)[1]
    return calendar["months"][month - 1]["days"]


def advance_story_clock(clock: dict, elapsed: dict, calendar_config: object = None) -> dict:
    """Advance absolute time; logical event ticks are managed separately."""
    cal = normalize_calendar(calendar_config)
    seconds = int(elapsed.get("total_seconds", 0) or 0)
    if seconds <= 0:
        return clock
    day_seconds = clock.get("second_of_day")
    if not isinstance(day_seconds, int):
        minute = clock.get("minute_of_day")
        if not isinstance(minute, int):
            minute = {"morning": 480, "afternoon": 840, "evening": 1140,
                      "night": 1380}.get(str(clock.get("time_of_day", "morning")).lower(), 480)
        day_seconds = minute * 60
    extra_days, second_of_day = divmod(day_seconds + seconds, 86400)
    year = max(1, int(clock.get("year", 1) or 1))
    month_count = 12 if cal["kind"] == "gregorian" else len(cal["months"])
    month = min(month_count, max(1, int(clock.get("month", 1) or 1)))
    day = max(1, int(clock.get("day", 1) or 1)) + extra_days
    while day > _month_days(cal, year, month):
        day -= _month_days(cal, year, month)
        month += 1
        if month > month_count:
            month = 1
            year += 1
    previous_seconds = int(clock.get("elapsed_seconds", int(clock.get("elapsed_minutes", 0) or 0) * 60) or 0)
    clock.update(year=year, month=month, day=day,
                 second_of_day=second_of_day, minute_of_day=second_of_day // 60,
                 elapsed_seconds=previous_seconds + seconds,
                 elapsed_minutes=(previous_seconds + seconds) // 60)
    hour = second_of_day // 3600
    clock["time_of_day"] = ("morning" if 5 <= hour < 12 else "afternoon" if hour < 17
                            else "evening" if hour < 22 else "night")
    for season in cal["seasons"]:
        if month in season["months"]:
            clock["season"] = season["name"]
            break
    return clock
