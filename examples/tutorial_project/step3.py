import sys

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
        fields: list[str] = line.split()
        if len(fields) != 6 or not fields[4].isdigit():
            malformed += 1
            continue
        size_text: str = fields[4]
        if len(size_text) > 19 or (len(size_text) == 19 and size_text > "9223372036854775807"):
            malformed += 1
            continue
        if not fields[5].isdigit():
            malformed += 1
            continue
        status: str = fields[3]
        size: int = int(size_text)
        millis: int = int(fields[5])
        counts[status] = counts.get(status, 0) + 1
        total_bytes += size
        if size > max_bytes:
            max_bytes = size
        total_millis += millis
        if millis > max_millis:
            max_millis = millis
    print("lines", lines)
    print("malformed", malformed)
    for status in sorted(counts):
        print(status, counts[status])
    print("bytes", total_bytes, max_bytes)
    print("millis", total_millis, max_millis)
    return 0

if __name__ == "__main__":
    sys.exit(main())
