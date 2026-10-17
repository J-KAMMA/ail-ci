import sys


def main() -> None:
    total = 0
    for line in sys.stdin:
        text = line.strip()
        if not text:
            print("invalid line: empty", file=sys.stderr)
            continue
        try:
            total += int(text)
        except ValueError:
            print(f"invalid line: {text}", file=sys.stderr)
    print(total)


if __name__ == "__main__":
    main()
