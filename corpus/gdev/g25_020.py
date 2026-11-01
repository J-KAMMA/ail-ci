# task: Use a match statement on dictionaries to process a fixed list of JSON-like event records and print a summary of each event type.
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Summary:
    count: int = 0
    users: set[str] = field(default_factory=set)
    total_amount: float = 0.0
    currencies: set[str] = field(default_factory=set)
    error_codes: set[int] = field(default_factory=set)
    keys_seen: set[str] = field(default_factory=set)


EVENTS: list[dict[str, object]] = [
    {"type": "login", "user": "alice", "ok": True},
    {"type": "click", "user": "alice", "x": 10, "y": 20},
    {"type": "purchase", "user": "bob", "amount": 19.99, "currency": "USD"},
    {"type": "click", "user": "bob", "x": 300, "y": 45},
    {"type": "purchase", "user": "alice", "amount": 5.5, "currency": "EUR"},
    {"type": "logout", "user": "alice"},
    {"type": "login", "user": "carol", "ok": False},
    {"type": "error", "code": 503, "message": "upstream timeout"},
    {"type": "purchase", "user": "carol", "amount": 42, "currency": "USD"},
    {"type": "scroll", "user": "bob", "delta": -120},
    {"type": "error", "code": 404, "message": "not found"},
    {"type": "mystery", "payload": [1, 2]},
    {"user": "dave"},
    {"type": "click", "user": "carol", "x": 5, "y": 5},
    {"type": "logout", "user": "bob"},
]


def touch(summaries: dict[str, Summary], kind: str) -> Summary:
    """Return the summary for an event kind, creating it if needed, and count the event."""
    summary = summaries.setdefault(kind, Summary())
    summary.count += 1
    return summary


def record(summaries: dict[str, Summary], event: dict[str, object]) -> None:
    """Classify one event record with structural pattern matching and update summaries."""
    match event:
        case {"type": "purchase", "user": str(user), "amount": (int() | float()) as amount,
              "currency": str(currency)}:
            summary = touch(summaries, "purchase")
            summary.users.add(user)
            summary.total_amount += float(amount)
            summary.currencies.add(currency)

        case {"type": "error", "code": int(code)}:
            summary = touch(summaries, "error")
            summary.error_codes.add(code)

        case {"type": "login", "user": str(user), "ok": bool(ok)}:
            summary = touch(summaries, "login")
            summary.users.add(user)
            summary.keys_seen.add("ok" if ok else "failed")

        case {"type": "click", "user": str(user), "x": int(), "y": int()}:
            summary = touch(summaries, "click")
            summary.users.add(user)

        case {"type": str(kind), "user": str(user), **rest}:
            summary = touch(summaries, kind)
            summary.users.add(user)
            summary.keys_seen.update(rest.keys())

        case {"type": str(kind), **rest}:
            summary = touch(summaries, kind)
            summary.keys_seen.update(rest.keys())

        case _:
            summary = touch(summaries, "<missing type>")
            summary.keys_seen.update(event.keys())


def format_summary(kind: str, summary: Summary) -> str:
    """Build a deterministic, human-readable line block for one event type."""
    lines = [f"{kind}: {summary.count} event(s)"]
    users = ", ".join(sorted(summary.users)) or "-"
    lines.append(f"  users: {users}")
    if summary.total_amount:
        currencies = ", ".join(sorted(summary.currencies)) or "-"
        lines.append(f"  total amount: {summary.total_amount:.2f} (currencies: {currencies})")
    if summary.error_codes:
        codes = ", ".join(str(code) for code in sorted(summary.error_codes))
        lines.append(f"  error codes: {codes}")
    if summary.keys_seen:
        keys = ", ".join(sorted(summary.keys_seen))
        lines.append(f"  fields seen: {keys}")
    return "\n".join(lines)


def main() -> None:
    summaries: dict[str, Summary] = {}
    for event in EVENTS:
        record(summaries, event)

    print(f"Processed {len(EVENTS)} events")
    print("-" * 40)
    for kind in sorted(summaries):
        print(format_summary(kind, summaries[kind]))
        print()


if __name__ == "__main__":
    main()
