# task: Count the occurrences of each HTTP status code in a hard-coded list of log lines and print a sorted summary.
import re
from collections import Counter


LOG_LINES: list[str] = [
    '192.168.1.10 - - [10/Oct/2023:13:55:36 +0000] "GET /index.html HTTP/1.1" 200 2326',
    '192.168.1.11 - - [10/Oct/2023:13:55:37 +0000] "GET /images/logo.png HTTP/1.1" 200 5123',
    '192.168.1.12 - - [10/Oct/2023:13:55:38 +0000] "POST /api/login HTTP/1.1" 401 128',
    '192.168.1.10 - - [10/Oct/2023:13:55:40 +0000] "GET /missing HTTP/1.1" 404 209',
    '10.0.0.5 - - [10/Oct/2023:13:56:01 +0000] "GET /api/data HTTP/1.1" 500 0',
    '10.0.0.6 - - [10/Oct/2023:13:56:03 +0000] "GET /old-page HTTP/1.1" 301 178',
    '10.0.0.7 - - [10/Oct/2023:13:56:05 +0000] "GET /index.html HTTP/1.1" 304 0',
    '192.168.1.11 - - [10/Oct/2023:13:56:09 +0000] "PUT /api/item/42 HTTP/1.1" 403 91',
    '192.168.1.13 - - [10/Oct/2023:13:56:12 +0000] "GET /api/data HTTP/1.1" 200 1044',
    '10.0.0.5 - - [10/Oct/2023:13:56:15 +0000] "DELETE /api/item/42 HTTP/1.1" 204 0',
    '192.168.1.10 - - [10/Oct/2023:13:56:18 +0000] "GET /missing HTTP/1.1" 404 209',
    '10.0.0.8 - - [10/Oct/2023:13:56:20 +0000] "GET /api/data HTTP/1.1" 503 57',
    '192.168.1.12 - - [10/Oct/2023:13:56:22 +0000] "GET /index.html HTTP/1.1" 200 2326',
    'malformed line without status',
    '10.0.0.9 - - [10/Oct/2023:13:56:25 +0000] "GET /old-page HTTP/1.1" 301 178',
    '10.0.0.5 - - [10/Oct/2023:13:56:30 +0000] "GET /api/data HTTP/1.1" 500 0',
]

# Matches the status code field that follows a quoted request line.
STATUS_PATTERN: re.Pattern[str] = re.compile(r'"[^"]*"\s+(\d{3})\s+\S+')


def extract_status(line: str) -> str | None:
    """Return the HTTP status code found in a log line, or None if absent."""
    match = STATUS_PATTERN.search(line)
    if match is None:
        return None
    return match.group(1)


def count_status_codes(lines: list[str]) -> Counter[str]:
    """Count occurrences of each HTTP status code across the given lines."""
    counts: Counter[str] = Counter()
    for line in lines:
        status = extract_status(line)
        if status is not None:
            counts[status] += 1
    return counts


def main() -> None:
    counts = count_status_codes(LOG_LINES)
    total = sum(counts.values())

    print("HTTP status code summary")
    print("-" * 28)
    for code in sorted(counts, key=int):
        print(f"{code}: {counts[code]}")
    print("-" * 28)
    print(f"Total: {total}")


if __name__ == "__main__":
    main()
