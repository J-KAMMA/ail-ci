import sys

def main() -> int:
    lines: int = 0
    malformed: int = 0
    counts: dict[str, int] = {}
    while True:
        line: str = sys.stdin.readline()
        if line == "":
            break
        lines += 1
        fields: list[str] = line.split()
        if len(fields) != 6 or not fields[4].isdigit():
            malformed += 1
            continue
        status: str = fields[3]
        counts[status] = counts.get(status, 0) + 1
    print("lines", lines)
    print("malformed", malformed)
    for status in sorted(counts):
        print(status, counts[status])
    return 0

if __name__ == "__main__":
    sys.exit(main())
