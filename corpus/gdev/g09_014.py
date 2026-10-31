# task: Count the binary strings of length 20 that contain no two consecutive 1s and print the count.
def count_no_adjacent_ones(length: int) -> int:
    """Return the number of binary strings of the given length with no two consecutive 1s."""
    if length == 0:
        return 1
    # ends_in_zero[i]: strings of current length ending in '0'
    # ends_in_one[i]: strings of current length ending in '1'
    ends_in_zero: int = 1  # the empty prefix, treated as ending in a non-1 state
    ends_in_one: int = 0
    for _ in range(length):
        # Append '0' to any valid string, or append '1' only after a '0'.
        ends_in_zero, ends_in_one = ends_in_zero + ends_in_one, ends_in_zero
    return ends_in_zero + ends_in_one


def main() -> None:
    n: int = 20
    print(count_no_adjacent_ones(n))


if __name__ == "__main__":
    main()
