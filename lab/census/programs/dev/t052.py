import sys


def main() -> None:
    if hasattr(sys, "set_int_max_str_digits"):
        sys.set_int_max_str_digits(0)

    n = int(sys.stdin.readline().strip())
    digits: str = str(2 ** (n * 10))
    digit_sum: int = sum(int(ch) for ch in digits)
    print(digit_sum)
    print(len(digits))


if __name__ == "__main__":
    main()
