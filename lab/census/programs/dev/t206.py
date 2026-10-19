import sys


def main() -> None:
    total: int = 0
    failures: int = 0
    for raw in sys.stdin.read().splitlines():
        line = raw.strip()
        try:
            total += int(line)
        except ValueError:
            failures += 1
    print(total)
    print(failures)


if __name__ == "__main__":
    main()
