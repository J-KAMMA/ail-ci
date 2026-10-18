import struct
import sys


def to_byte_list(value: int) -> list[int]:
    magnitude = abs(value)
    length = max(1, (magnitude.bit_length() + 7) // 8)
    data = magnitude.to_bytes(length, "big", signed=False)
    assert int.from_bytes(data, "big", signed=False) == magnitude
    return list(data)


def main() -> None:
    tokens = sys.stdin.read().split()
    n = int(tokens[0])
    numbers = [int(token) for token in tokens[1 : n + 1]]
    for value in numbers:
        print(to_byte_list(value))
        if value < 2**32:
            packed = struct.pack(">I", value)
            assert int.from_bytes(packed, "big", signed=False) == value
            print(list(packed))


if __name__ == "__main__":
    main()
