import sys
from typing import Iterable


def parse_valid_ints(lines: Iterable[str]) -> list[int]:
    values: list[int] = []
    for line in lines:
        text = line.strip()
        if not text:
            continue
        try:
            values.append(int(text))
        except ValueError:
            continue
    return values


def main() -> None:
    total = sum(parse_valid_ints(sys.stdin))
    if total < 0:
        print(total)
        raise ValueError(f"negative sum: {total}")
    print("fine")


if __name__ == "__main__":
    main()
