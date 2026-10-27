# task: Write a script that uses list slicing to check whether a hardcoded list is a palindrome and prints the result for several test lists.
from typing import Sequence, Any


def is_palindrome(items: Sequence[Any]) -> bool:
    """Return True if the sequence reads the same forwards and backwards."""
    return list(items) == list(items)[::-1]


def main() -> None:
    test_cases: list[tuple[str, list[Any]]] = [
        ("Empty list", []),
        ("Single element", [7]),
        ("Simple palindrome of integers", [1, 2, 3, 2, 1]),
        ("Non-palindrome of integers", [1, 2, 3, 4, 5]),
        ("Even-length palindrome", [4, 8, 8, 4]),
        ("Even-length non-palindrome", [4, 8, 9, 4]),
        ("Palindrome of strings", ["a", "b", "c", "b", "a"]),
        ("Non-palindrome of strings", ["level", "noon", "python"]),
        ("Mixed types palindrome", [1, "x", 2.5, "x", 1]),
        ("Repeated values", [5, 5, 5, 5]),
        ("Boolean palindrome", [True, False, True]),
        ("Nested list palindrome", [[1, 2], [3], [1, 2]]),
    ]

    for label, data in test_cases:
        result = is_palindrome(data)
        print(f"{label}: {data} -> {'palindrome' if result else 'not a palindrome'}")


if __name__ == "__main__":
    main()
