import sys


def divisors(n: int) -> list[int]:
    result: list[int] = []
    i = 1
    while i * i <= n:
        if n % i == 0:
            result.append(i)
            if i != n // i:
                result.append(n // i)
        i += 1
    result.sort()
    return result


def main() -> None:
    n = int(sys.stdin.readline().strip())
    ds = divisors(n)
    print(" ".join(map(str, ds)))
    print(len(ds))
    print(sum(ds))


if __name__ == "__main__":
    main()
