import math


def divisors(n: int) -> list[int]:
    small: list[int] = []
    large: list[int] = []
    for i in range(1, math.isqrt(n) + 1):
        if n % i == 0:
            small.append(i)
            if i != n // i:
                large.append(n // i)
    return small + large[::-1]


def main() -> None:
    n = int(input().strip())
    divs = divisors(n)
    print(" ".join(map(str, divs)))
    print(len(divs))
    print(sum(divs))


if __name__ == "__main__":
    main()
