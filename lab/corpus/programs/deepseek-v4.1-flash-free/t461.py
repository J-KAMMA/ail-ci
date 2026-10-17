import sys


def is_integer(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    try:
        int(stripped)
    except ValueError:
        return False
    return True


def main() -> None:
    valid_count = 0
    has_invalid = False

    for line in sys.stdin.read().splitlines():
        if is_integer(line):
            valid_count += 1
        else:
            has_invalid = True

    if has_invalid:
        print(valid_count)
        sys.exit(2)


if __name__ == "__main__":
    main()
