import sys

BITS = 16


def twos_complement(value: int, bits: int = BITS) -> str:
    return format(value & ((1 << bits) - 1), f"0{bits}b")


def main() -> None:
    data = sys.stdin.buffer.read().split()
    if not data:
        return

    count = int(data[0])
    numbers = [int(token) for token in data[1:1 + count]]

    lines = []
    for x in numbers:
        position = x.bit_length()
        if -32768 <= x <= 32767:
            representation = twos_complement(-x)
        else:
            representation = "-"
        lines.append(f"{x} {position} {representation}")

    sys.stdout.write("\n".join(lines) + ("\n" if lines else ""))


if __name__ == "__main__":
    main()
