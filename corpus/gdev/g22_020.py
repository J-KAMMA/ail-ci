# task: Find the two numbers that appear once in a list where all other numbers appear twice using XOR and a separating bit mask, then print them.
from collections.abc import Sequence


def find_two_singles(nums: Sequence[int]) -> tuple[int, int]:
    """Return the two values that appear exactly once; all others appear twice."""
    # XOR of all numbers equals XOR of the two unique values (pairs cancel out).
    xor_all = 0
    for n in nums:
        xor_all ^= n

    # The lowest set bit of xor_all is set in exactly one of the two unique values,
    # so it separates them into two groups.
    separator = xor_all & -xor_all

    first = 0
    second = 0
    for n in nums:
        if n & separator:
            first ^= n
        else:
            second ^= n

    return (min(first, second), max(first, second))


def main() -> None:
    numbers: list[int] = [4, 1, 2, 1, 2, 3, 5, 4, 6, 6, 9, 9, 12, 7, 7, 12, 10, 10]
    a, b = find_two_singles(numbers)
    print(f"Numbers appearing once: {a} and {b}")


if __name__ == "__main__":
    main()
