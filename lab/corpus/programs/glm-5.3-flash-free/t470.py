import sys


def is_power_of_two(m: int) -> bool:
    return m > 0 and m & (m - 1) == 0


def main() -> None:
    data = sys.stdin.read().split()
    n = int(data[0])
    nums = [int(tok) for tok in data[1 : 1 + n]]

    lines: list[str] = []
    powers = 0
    for x in nums:
        m = abs(x)
        a = m & (m - 1)
        b = m & -m
        c = m ^ (m >> 1)
        bl = m.bit_length()
        lines.append(f"{a} {b} {c} {bl}")
        if is_power_of_two(m):
            powers += 1

    for line in lines:
        print(line)
    print(powers)


if __name__ == "__main__":
    main()
