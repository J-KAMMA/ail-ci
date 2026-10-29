# task: Swap the odd and even bit positions of 0xAAAA5555 and print the result in 32-bit binary.
def swap_odd_even_bits(value: int) -> int:
    """Swap each pair of adjacent bits (odd and even positions) in a 32-bit value."""
    even_mask: int = 0x55555555  # bits at even positions (0, 2, 4, ...)
    odd_mask: int = 0xAAAAAAAA   # bits at odd positions (1, 3, 5, ...)
    return ((value & odd_mask) >> 1) | ((value & even_mask) << 1)


def main() -> None:
    value: int = 0xAAAA5555
    result: int = swap_odd_even_bits(value) & 0xFFFFFFFF
    print(format(result, "032b"))


if __name__ == "__main__":
    main()
