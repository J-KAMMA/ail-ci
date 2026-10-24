# task: Compute the sum of the digits of 100! and print it.
import math


def digit_sum(n: int) -> int:
    return sum(int(ch) for ch in str(n))


def main() -> None:
    result: int = digit_sum(math.factorial(100))
    print(result)


if __name__ == "__main__":
    main()
