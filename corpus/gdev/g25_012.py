# task: Use a match statement with guard clauses to categorize a fixed list of integers into negative, zero, small positive, and large positive groups.
from typing import Dict, List


SMALL_POSITIVE_LIMIT: int = 100


def categorize(value: int) -> str:
    match value:
        case int(v) if v < 0:
            return "negative"
        case 0:
            return "zero"
        case int(v) if 0 < v <= SMALL_POSITIVE_LIMIT:
            return "small positive"
        case int(v) if v > SMALL_POSITIVE_LIMIT:
            return "large positive"
        case _:
            raise TypeError(f"unexpected value: {value!r}")


def main() -> None:
    numbers: List[int] = [-42, 0, 7, 100, 101, -1, 2500, 3, 0, -999, 58, 1000000]

    groups: Dict[str, List[int]] = {
        "negative": [],
        "zero": [],
        "small positive": [],
        "large positive": [],
    }

    for number in numbers:
        groups[categorize(number)].append(number)

    for label, members in groups.items():
        print(f"{label}: {members}")

    print(f"total: {sum(len(m) for m in groups.values())}")


if __name__ == "__main__":
    main()
