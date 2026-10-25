# task: Use itertools.takewhile and itertools.dropwhile to split a hardcoded integer list at the first value exceeding a threshold and print both parts.
import itertools
from typing import Iterable


def split_at_first_exceeding(values: list[int], threshold: int) -> tuple[list[int], list[int]]:
    """Split values into (prefix, rest) at the first value greater than threshold."""
    prefix: list[int] = list(itertools.takewhile(lambda x: x <= threshold, values))
    rest: list[int] = list(itertools.dropwhile(lambda x: x <= threshold, values))
    return prefix, rest


def format_list(label: str, items: Iterable[int]) -> str:
    return f"{label}: {list(items)}"


def main() -> None:
    data: list[int] = [3, 8, 2, 7, 15, 4, 9, 1, 22, 6]
    threshold: int = 10

    prefix, rest = split_at_first_exceeding(data, threshold)

    print(f"Original: {data}")
    print(f"Threshold: {threshold}")
    print(format_list("Prefix (values <= threshold)", prefix))
    print(format_list("Rest (starting at first value > threshold)", rest))


if __name__ == "__main__":
    main()
