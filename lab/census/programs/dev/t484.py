import string
import sys


def main() -> None:
    data: str = sys.stdin.read()
    lines: list[str] = data.splitlines()

    table: dict[int, None] = str.maketrans("", "", string.punctuation)
    cleaned_lines: list[str] = [line.translate(table) for line in lines]

    allowed: frozenset[str] = frozenset(string.ascii_letters + string.digits)
    count: int = sum(1 for line in cleaned_lines for ch in line if ch in allowed)

    for line in cleaned_lines:
        print(line)
    print(f"alnum: {count}")


if __name__ == "__main__":
    main()
