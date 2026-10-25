def fact(n):
    import math
    return math.factorial(n)


def comb_row(n):
    from math import comb
    return [comb(n, k) for k in range(n + 1)]


def main():
    print(fact(30))
    print(fact(25) // fact(23))
    print(comb_row(70)[35])
    import math
    print(math.factorial(21), math.comb(100, 50), math.perm(25, 20))


main()
