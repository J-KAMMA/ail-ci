# task: Parse embedded Apache-style access log lines and count requests per HTTP status code, printing the codes in ascending order.
import re
from collections import Counter
from typing import Iterable

LOG_LINES: list[str] = [
    '192.168.1.10 - - [10/Oct/2023:13:55:36 +0000] "GET /index.html HTTP/1.1" 200 2326',
    '192.168.1.11 - - [10/Oct/2023:13:55:37 +0000] "GET /images/logo.png HTTP/1.1" 200 15342',
    '192.168.1.12 - alice [10/Oct/2023:13:55:40 +0000] "POST /login HTTP/1.1" 302 0',
    '10.0.0.5 - - [10/Oct/2023:13:56:01 +0000] "GET /missing HTTP/1.1" 404 209',
    '10.0.0.6 - - [10/Oct/2023:13:56:03 +0000] "GET /admin HTTP/1.1" 403 153',
    '10.0.0.7 - bob [10/Oct/2023:13:56:10 +0000] "PUT /api/item/42 HTTP/1.1" 500 87',
    '10.0.0.8 - - [10/Oct/2023:13:56:15 +0000] "GET /about.html HTTP/1.0" 200 4096',
    '10.0.0.9 - - [10/Oct/2023:13:56:20 +0000] "GET /api/items HTTP/1.1" 304 0',
    '10.0.0.9 - - [10/Oct/2023:13:56:22 +0000] "DELETE /api/item/42 HTTP/1.1" 204 0',
    '172.16.0.3 - - [10/Oct/2023:13:57:00 +0000] "GET / HTTP/1.1" 200 1024',
    '172.16.0.4 - - [10/Oct/2023:13:57:05 +0000] "GET /old-page HTTP/1.1" 301 178',
    '172.16.0.4 - - [10/Oct/2023:13:57:06 +0000] "GET /index.html HTTP/1.1" 200 2326',
    '172.16.0.5 - - [10/Oct/2023:13:57:30 +0000] "GET /api/status HTTP/1.1" 503 95',
    '172.16.0.5 - - [10/Oct/2023:13:57:31 +0000] "GET /api/status HTTP/1.1" 200 27',
    '172.16.0.6 - - [10/Oct/2023:13:58:02 +0000] "GET /search?q=test HTTP/1.1" 200 5120',
    '172.16.0.7 - - [10/Oct/2023:13:58:10 +0000] "GET /files/report.pdf HTTP/1.1" 206 1024',
    '172.16.0.8 - - [10/Oct/2023:13:58:15 +0000] "OPTIONS * HTTP/1.1" 200 0',
    'this line is malformed and should be skipped',
    '',
    '172.16.0.9 - - [10/Oct/2023:13:59:00 +0000] "GET /api/items HTTP/1.1" 200 812',
]

LOG_PATTERN = re.compile(
    r'^(?P<host>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] '
    r'"(?P<request>(?:[^"\\]|\\.)*)" '
    r'(?P<status>\d{3}) (?P<size>\S+)'
)


def parse_status_counts(lines: Iterable[str]) -> Counter[int]:
    """Count requests per HTTP status code, skipping unparseable lines."""
    counts: Counter[int] = Counter()
    for line in lines:
        match = LOG_PATTERN.match(line.strip())
        if match is None:
            continue
        counts[int(match.group("status"))] += 1
    return counts


def main() -> None:
    counts = parse_status_counts(LOG_LINES)
    for status in sorted(counts):
        print(f"{status} {counts[status]}")


if __name__ == "__main__":
    main()
