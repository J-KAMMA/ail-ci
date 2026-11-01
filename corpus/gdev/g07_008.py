# task: Write a script that interleaves two hardcoded lists of different lengths element by element and appends the leftover items from the longer list.
from typing import List, TypeVar

T = TypeVar("T")


def interleave_with_leftovers(first: List[T], second: List[T]) -> List[T]:
    """Interleave two lists element by element, then append leftover items
    from the longer list."""
    result: List[T] = []
    for a, b in zip(first, second):
        result.append(a)
        result.append(b)
    longer = first if len(first) > len(second) else second
    result.extend(longer[min(len(first), len(second)):])
    return result


def main() -> None:
    letters: List[str] = ["a", "b", "c", "d", "e"]
    numbers: List[str] = ["1", "2", "3"]

    combined = interleave_with_leftovers(letters, numbers)
    print("Interleaved result:", combined)
    print("Length:", len(combined))


if __name__ == "__main__":
    main()
