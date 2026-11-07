# task: Multiply two integers using shift-and-add logic, verify the result against the * operator, and print both values.
def shift_and_add_multiply(a: int, b: int) -> int:
    """Multiply two integers using only shifts, additions, and bit tests."""
    negative = (a < 0) != (b < 0)
    x = abs(a)
    y = abs(b)

    result = 0
    while y:
        if y & 1:
            result += x
        x <<= 1
        y >>= 1

    return -result if negative else result


def main() -> None:
    test_pairs: list[tuple[int, int]] = [
        (0, 7),
        (1, 1),
        (13, 11),
        (-9, 6),
        (7, -8),
        (-12, -15),
        (123456, 654321),
        (2**20 + 3, 2**10 - 7),
    ]

    all_match = True
    for a, b in test_pairs:
        shifted = shift_and_add_multiply(a, b)
        expected = a * b
        matches = shifted == expected
        all_match = all_match and matches

        print(f"a = {a}, b = {b}")
        print(f"  shift-and-add result: {shifted}")
        print(f"  operator * result:    {expected}")
        print(f"  match: {matches}")

    print(f"All results match: {all_match}")


if __name__ == "__main__":
    main()
