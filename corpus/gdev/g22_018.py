# task: Determine which of several hardcoded 32-bit integers have alternating bit patterns and print the results.
"""Determine which hardcoded 32-bit integers have alternating bit patterns.

A value has an alternating bit pattern when every pair of adjacent bits
(within the 32-bit width) differs, e.g. 0101...01 or 1010...10.
"""

from __future__ import annotations

BIT_WIDTH: int = 32
MASK: int = (1 << BIT_WIDTH) - 1

# Hardcoded test values (all treated as unsigned 32-bit integers).
TEST_VALUES: tuple[int, ...] = (
    0x55555555,  # 0101...0101 -> alternating
    0xAAAAAAAA,  # 1010...1010 -> alternating
    0x2AAAAAAA,  # 0010...1010 -> alternating (top bits 0,0 break it)
    0x12345678,  # not alternating
    0x00000000,  # all zeros -> not alternating
    0xFFFFFFFF,  # all ones -> not alternating
    0x7FFFFFFF,  # 0111...1111 -> not alternating
    0x80000000,  # 1000...0000 -> not alternating
    0x00000001,  # single set bit -> not alternating
    0x00000002,  # 0000...0010 -> not alternating
    0x9C9C9C9C,  # repeated nibbles, not alternating
    0x6DB6DB6D,  # 0110 1101 1011 ... -> not alternating
    0x40000000,  # 0100...0000 -> not alternating
    0x00000005,  # 0000...0101 -> not alternating (leading zeros repeat)
)


def is_alternating(value: int) -> bool:
    """Return True if every adjacent pair of bits in a 32-bit value differs."""
    value &= MASK
    for i in range(BIT_WIDTH - 1):
        bit_low: int = (value >> i) & 1
        bit_high: int = (value >> (i + 1)) & 1
        if bit_low == bit_high:
            return False
    return True


def format_binary(value: int) -> str:
    """Format a value as a 32-bit binary string with underscores every 8 bits."""
    bits: str = format(value & MASK, f"0{BIT_WIDTH}b")
    return "_".join(bits[i:i + 8] for i in range(0, BIT_WIDTH, 8))


def main() -> None:
    alternating_values: list[int] = []

    print(f"Checking {len(TEST_VALUES)} hardcoded {BIT_WIDTH}-bit values:")
    print("-" * 60)
    for value in TEST_VALUES:
        result: bool = is_alternating(value)
        if result:
            alternating_values.append(value)
        print(f"0x{value & MASK:08X}  {format_binary(value)}  "
              f"alternating={result}")
    print("-" * 60)

    print(f"Number alternating: {len(alternating_values)} of {len(TEST_VALUES)}")
    listed: str = ", ".join(f"0x{v & MASK:08X}" for v in alternating_values)
    print(f"Alternating values: {listed if listed else 'none'}")


if __name__ == "__main__":
    main()
