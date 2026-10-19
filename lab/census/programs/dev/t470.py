import sys


def main() -> None:
    data: list[str] = sys.stdin.read().split()
    if not data:
        return

    count: int = int(data[0])
    values: list[int] = [int(tok) for tok in data[1:1 + count]]

    powers_of_two: int = 0
    for value in values:
        m: int = abs(value)
        clear_lowest: int = m & (m - 1)
        lowest_bit: int = m & -m
        gray: int = m ^ (m >> 1)
        bits: int = m.bit_length()
        print(f"{m} {clear_lowest} {lowest_bit} {gray} {bits}")
        if m > 0 and clear_lowest == 0:
            powers_of_two += 1

    print(f"powers of two: {powers_of_two}")


if __name__ == "__main__":
    main()
