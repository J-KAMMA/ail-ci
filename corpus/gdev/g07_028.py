# task: Write a script that splits a hardcoded list into two halves and interleaves them in reverse-second-half order, printing the result.
def interleave_reversed_halves(items: list[int]) -> list[int]:
    """Split items into two halves, reverse the second half, and interleave.

    For odd-length input, the first half receives the extra element.
    Any leftover element from the first half is appended at the end.
    """
    mid: int = (len(items) + 1) // 2
    first: list[int] = items[:mid]
    second: list[int] = items[mid:][::-1]

    result: list[int] = []
    for i in range(max(len(first), len(second))):
        if i < len(first):
            result.append(first[i])
        if i < len(second):
            result.append(second[i])
    return result


def main() -> None:
    data: list[int] = [10, 20, 30, 40, 50, 60, 70]
    mid: int = (len(data) + 1) // 2

    print(f"Original:          {data}")
    print(f"First half:        {data[:mid]}")
    print(f"Second half:       {data[mid:]}")
    print(f"Reversed second:   {data[mid:][::-1]}")
    print(f"Interleaved:       {interleave_reversed_halves(data)}")


if __name__ == "__main__":
    main()
