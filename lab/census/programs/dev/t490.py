import sys


def main() -> None:
    text: str = sys.stdin.read()

    # Unique characters, sorted by code point (sorting str sorts by code point).
    chars: list[str] = sorted(set(text))
    # Keep only characters whose code point is above 127.
    high: list[str] = [ch for ch in chars if ord(ch) > 127]

    for ch in high:
        print(f"{ch} {ord(ch)}")

    count: int = len(high)
    max_code: int = max((ord(ch) for ch in high), default=0)

    print(f"count {count}")
    print(f"max {max_code}")


if __name__ == "__main__":
    main()
