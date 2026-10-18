import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    values = [int(x) for x in data[1:1 + n]]

    powers_of_two = 0
    for value in values:
        m = abs(value)
        print(m & (m - 1), m & -m, m ^ (m >> 1), m.bit_length())
        if m > 0 and (m & (m - 1)) == 0:
            powers_of_two += 1

    print(powers_of_two)


if __name__ == "__main__":
    main()
