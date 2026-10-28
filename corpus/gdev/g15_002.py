# task: Parse a list of strings into integers, collecting ValueError failures into a separate list and printing the counts of successes and failures.
from typing import Iterable


def parse_integers(items: Iterable[str]) -> tuple[list[int], list[str]]:
    """Parse strings into integers, collecting failures separately."""
    successes: list[int] = []
    failures: list[str] = []
    for item in items:
        try:
            successes.append(int(item))
        except ValueError:
            failures.append(item)
    return successes, failures


def main() -> None:
    data: list[str] = [
        "10",
        "abc",
        "-7",
        "3.14",
        "  42  ",
        "",
        "+15",
        "1_000",
        "twelve",
        "0x1F",
        "-0",
        "99999999999999999999",
    ]

    successes, failures = parse_integers(data)

    print(f"Total inputs: {len(data)}")
    print(f"Successes: {len(successes)}")
    print(f"Failures: {len(failures)}")
    print(f"Parsed values: {successes}")
    print(f"Failed inputs: {failures}")


if __name__ == "__main__":
    main()
