# task: Use a custom JSONEncoder subclass to serialize datetime.date objects in a hardcoded list as ISO-formatted strings.
import datetime
import json
from typing import Any


class DateEncoder(json.JSONEncoder):
    """JSON encoder that serializes datetime.date objects as ISO-formatted strings."""

    def default(self, o: Any) -> Any:
        if isinstance(o, datetime.date):
            return o.isoformat()
        return super().default(o)


def main() -> None:
    events: list[dict[str, Any]] = [
        {"name": "Project kickoff", "date": datetime.date(2024, 1, 15)},
        {"name": "Design review", "date": datetime.date(2024, 2, 28)},
        {"name": "Beta release", "date": datetime.date(2024, 6, 1)},
        {"name": "Public launch", "date": datetime.date(2024, 9, 30)},
        {"name": "Retrospective", "date": datetime.date(2024, 12, 31)},
    ]

    payload: dict[str, Any] = {
        "dates": [event["date"] for event in events],
        "events": events,
        "count": len(events),
    }

    print(json.dumps(payload, cls=DateEncoder, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
