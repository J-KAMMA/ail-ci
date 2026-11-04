import sys

class Entry:
    def __init__(self, timestamp: str, method: str, path: str, status: str, size: int, millis: int) -> None:
        self.timestamp = timestamp
        self.method = method
        self.path = path
        self.status = status
        self.size = size
        self.millis = millis

def parse(line: str) -> Entry | None:
    fields: list[str] = line.split()
    if len(fields) != 6 or not fields[4].isdigit():
        return None
    size_text: str = fields[4]
    if len(size_text) > 19 or (len(size_text) == 19 and size_text > "9223372036854775807"):
        return None
    if not fields[5].isdigit():
        return None
    return Entry(fields[0], fields[1], fields[2], fields[3], int(size_text), int(fields[5]))

def main() -> int:
    lines: int = 0
    malformed: int = 0
    counts: dict[str, int] = {}
    total_bytes: int = 0
    max_bytes: int = 0
    total_millis: int = 0
    max_millis: int = 0
    while True:
        line: str = sys.stdin.readline()
        if line == "":
            break
        lines += 1
        entry = parse(line)
        if entry is None:
            malformed += 1
            continue
        counts[entry.status] = counts.get(entry.status, 0) + 1
        total_bytes += entry.size
        if entry.size > max_bytes:
            max_bytes = entry.size
        total_millis += entry.millis
        if entry.millis > max_millis:
            max_millis = entry.millis
    print("lines", lines)
    print("malformed", malformed)
    for status in sorted(counts):
        print(status, counts[status])
    print("bytes", total_bytes, max_bytes)
    print("millis", total_millis, max_millis)
    return 0

if __name__ == "__main__":
    sys.exit(main())
