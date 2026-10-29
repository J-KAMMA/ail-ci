# task: Count the binary strings of length 16 that contain no two adjacent zeros and print the count.
def count_no_adjacent_zeros(length: int) -> int:
    """Count binary strings of the given length with no two adjacent zeros."""
    if length == 0:
        return 1
    # ends_in_one: strings of current length ending in '1'
    # ends_in_zero: strings of current length ending in '0'
    ends_in_one: int = 1
    ends_in_zero: int = 1
    for _ in range(length - 1):
        # Append '1' to anything; append '0' only to strings ending in '1'.
        ends_in_one, ends_in_zero = ends_in_one + ends_in_zero, ends_in_one
    return ends_in_one + ends_in_zero


def main() -> None:
    count: int = count_no_adjacent_zeros(16)
    print(count)


if __name__ == "__main__":
    main()
