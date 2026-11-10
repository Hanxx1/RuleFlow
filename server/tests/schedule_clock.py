"""Opt-in scheduling-only clock; authentication uses the real wall clock."""
from datetime import datetime


def freeze_schedule_clock(monkeypatch, instant):
    from app.api import planning
    from app.services import schedule_drafts

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls.instant.astimezone(tz) if tz else cls.instant.replace(tzinfo=None)

    FrozenDateTime.instant = datetime.fromisoformat(instant)
    monkeypatch.setattr(planning, 'datetime', FrozenDateTime)
    monkeypatch.setattr(schedule_drafts, 'datetime', FrozenDateTime)
    return FrozenDateTime
