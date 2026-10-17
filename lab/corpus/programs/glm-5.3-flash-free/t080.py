import sys


def byte_length(word: str) -> int:
    return len(word.encode("utf-8"))


def main() -> None:
    words: list[str] = sys.stdin.read().split()
    if not words:
        return

    by_chars = max(words, key=len)
    by_bytes = max(words, key=byte_length)

    print(f"Longest by characters: {by_chars} {len(by_chars)}")
    print(f"Longest by UTF-8 bytes: {by_bytes} {byte_length(by_bytes)}")


if __name__ == "__main__":
    main()
