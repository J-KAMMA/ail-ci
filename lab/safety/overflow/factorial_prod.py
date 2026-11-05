import math


def main() -> None:
    factors = []
    for i in range(2, 8):
        factors.append(i)
    print(math.prod(factors))
    words = [0] * 21
    print(math.factorial(len(words) - 1))
    sevens = [7] * 25
    print(math.prod(sevens), math.factorial(len(words)))


main()
