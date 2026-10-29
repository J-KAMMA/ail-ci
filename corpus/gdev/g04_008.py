# task: Implement radix sort (LSD) on a hardcoded list of three-digit integers and print the list after each digit pass.
from typing import List


def counting_pass(values: List[int], exp: int) -> List[int]:
    """Stable counting sort of values by the digit at position exp (1, 10, 100)."""
    base = 10
    count: List[int] = [0] * base
    for v in values:
        digit = (v // exp) % base
        count[digit] += 1

    # Convert counts to starting positions.
    for d in range(1, base):
        count[d] += count[d - 1]

    output: List[int] = [0] * len(values)
    # Traverse backwards to keep the sort stable.
    for v in reversed(values):
        digit = (v // exp) % base
        count[digit] -= 1
        output[count[digit]] = v
    return output


def radix_sort_lsd(values: List[int], digits: int = 3) -> List[int]:
    """Sort non-negative integers with LSD radix sort, printing after each pass."""
    result = list(values)
    exp = 1
    for pass_number in range(1, digits + 1):
        result = counting_pass(result, exp)
        print(f"After pass {pass_number} (digit place {exp}): {result}")
        exp *= 10
    return result


def main() -> None:
    data: List[int] = [329, 457, 657, 839, 436, 720, 355, 101, 999, 5, 42, 318]
    print(f"Original: {data}")
    sorted_data = radix_sort_lsd(data, digits=3)
    print(f"Sorted:   {sorted_data}")


if __name__ == "__main__":
    main()
