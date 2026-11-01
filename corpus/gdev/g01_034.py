# task: Parse embedded key=value log tokens and total the transferred bytes for each user field.
import re
from collections import defaultdict
from typing import Iterable

LOG_LINES: list[str] = [
    "2024-05-01T10:00:00Z level=info user=alice action=upload bytes=1024 path=/a.txt",
    "2024-05-01T10:00:05Z level=info user=bob action=download bytes=2048 path=/b.bin",
    "2024-05-01T10:00:09Z level=warn user=alice action=download bytes=512",
    '2024-05-01T10:01:00Z level=info user="carol smith" action=upload bytes=4096',
    "2024-05-01T10:01:30Z level=info user=bob action=upload bytes=not_a_number",
    "2024-05-01T10:02:00Z level=error action=download bytes=999",
    "2024-05-01T10:02:15Z level=info user=dave action=download bytes=0",
    "malformed line without any key value tokens",
    "2024-05-01T10:03:00Z level=info user=alice action=upload bytes=8192 path=/c.zip",
    '2024-05-01T10:03:30Z level=info user="carol smith" action=download bytes=1500',
    "2024-05-01T10:04:00Z level=info user=bob action=download bytes=-50",
    "2024-05-01T10:04:10Z level=debug user=erin action=upload bytes=300 note=\"ok\"",
]

TOKEN_RE = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|\S+)')


def parse_fields(line: str) -> dict[str, str]:
    """Extract key=value pairs from a log line, unquoting quoted values."""
    fields: dict[str, str] = {}
    for key, raw in TOKEN_RE.findall(line):
        if len(raw) >= 2 and raw.startswith('"') and raw.endswith('"'):
            fields[key] = raw[1:-1]
        else:
            fields[key] = raw
    return fields


def total_bytes_per_user(lines: Iterable[str]) -> tuple[dict[str, int], int]:
    """Sum the 'bytes' field for each 'user' field.

    Returns the per-user totals and the number of lines skipped.
    """
    totals: defaultdict[str, int] = defaultdict(int)
    skipped = 0
    for line in lines:
        fields = parse_fields(line)
        user = fields.get("user")
        raw_bytes = fields.get("bytes")
        if not user or raw_bytes is None:
            skipped += 1
            continue
        try:
            amount = int(raw_bytes)
        except ValueError:
            skipped += 1
            continue
        if amount < 0:
            skipped += 1
            continue
        totals[user] += amount
    return dict(totals), skipped


def main() -> None:
    totals, skipped = total_bytes_per_user(LOG_LINES)
    print("Transferred bytes per user:")
    for user in sorted(totals):
        print(f"  {user}: {totals[user]}")
    grand_total = sum(totals.values())
    print(f"Total across users: {grand_total}")
    print(f"Lines skipped: {skipped}")


if __name__ == "__main__":
    main()
