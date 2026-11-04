import sys

def main() -> int:
    lines: int = 0
    malformed: int = 0
    while True:
        line: str = sys.stdin.readline()
        if line == "":
            break
        lines += 1
        fields: list[str] = line.split()
        if len(fields) != 6 or not fields[4].isdigit():
            malformed += 1
    print("lines", lines)
    print("malformed", malformed)
    return 0

if __name__ == "__main__":
    sys.exit(main())
