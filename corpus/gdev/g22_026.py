# task: Pack a fixed list of booleans into bytes using bit shifts and then unpack them, printing the packed bytes in hex.
from typing import Sequence


def pack_bools(bits: Sequence[bool]) -> bytes:
    """Pack a sequence of booleans into bytes, MSB-first within each byte."""
    result = bytearray()
    for start in range(0, len(bits), 8):
        chunk = bits[start:start + 8]
        byte_value = 0
        for i, bit in enumerate(chunk):
            if bit:
                byte_value |= 1 << (7 - i)
        result.append(byte_value)
    return bytes(result)


def unpack_bools(data: bytes, count: int) -> list[bool]:
    """Unpack the first `count` booleans from packed bytes, MSB-first."""
    bits: list[bool] = []
    for index in range(count):
        byte_value = data[index // 8]
        shift = 7 - (index % 8)
        bits.append(bool((byte_value >> shift) & 1))
    return bits


def main() -> None:
    flags: list[bool] = [
        True, False, True, True, False, False, False, True,
        False, True, True, False, True,
        True, True, True, False, False, False, False, False,
        True,
    ]

    packed: bytes = pack_bools(flags)
    print(f"Bit count: {len(flags)}")
    print(f"Packed bytes (hex): {packed.hex(' ')}")

    unpacked: list[bool] = unpack_bools(packed, len(flags))
    print(f"Unpacked matches original: {unpacked == flags}")

    for line_start in range(0, len(unpacked), 8):
        segment = unpacked[line_start:line_start + 8]
        rendered = "".join("1" if b else "0" for b in segment)
        print(f"Bits {line_start:2d}-{line_start + len(segment) - 1:2d}: {rendered}")


if __name__ == "__main__":
    main()
