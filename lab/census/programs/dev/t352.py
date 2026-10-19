from typing import Sequence, Union

Number = Union[int, float]


def median(values: Sequence[int]) -> Number:
    """Return the median of a non-empty sequence of integers.

    Odd-length input yields the middle element (an int). Even-length input
    yields the mean of the two middle elements, as an int when that mean is
    integral and as a float otherwise.
    """
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return ordered[mid]
    total = ordered[mid - 1] + ordered[mid]
    if total % 2 == 0:
        return total // 2
    return total / 2


def main() -> None:
    line = input().strip() if True else ""
    try:
        data = [int(tok) for tok in line.split()]
    except EOFError:
        data = []
    if not data:
        return

    chunks = [data[i:i + 5] for i in range(0, len(data), 5)]
    medians = [median(chunk) for chunk in chunks]
    median_of_medians = median(medians)
    exact = median(data)

    print(medians)
    print(median_of_medians)
    print(exact)


if __name__ == "__main__":
    main()
