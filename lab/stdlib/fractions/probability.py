from fractions import Fraction


def fact(n):
    r = 1
    for k in range(2, n + 1):
        r = r * k
    return r


def choose(n, k):
    if k < 0 or k > n:
        return 0
    return fact(n) // (fact(k) * fact(n - k))


def main():
    red = 5
    blue = 3
    total = red + blue
    p_two_red = Fraction(choose(red, 2), choose(total, 2))
    p_same = Fraction(choose(red, 2) + choose(blue, 2), choose(total, 2))
    print(p_two_red, float(p_two_red))
    print(p_same, float(p_same))
    print(p_two_red + p_same)
    outcomes = {}
    for r in range(red + 1):
        for b in range(blue + 1):
            if r + b == 2:
                outcomes[(r, b)] = Fraction(choose(red, r) * choose(blue, b), choose(total, 2))
    for key in sorted(outcomes):
        print(key, outcomes[key], float(outcomes[key]))
    s = Fraction(0)
    for key in outcomes:
        s = s + outcomes[key]
    print(s)
    try:
        print(outcomes[(9, 9)])
    except KeyError as exc:
        print("KeyError", str(exc))


main()
