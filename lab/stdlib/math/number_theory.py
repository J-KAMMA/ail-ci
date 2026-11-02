import math

def choose(n, k):
    return math.comb(n, k)

def arrangements(n, k):
    return math.perm(n, k)

def factorial_table(limit):
    rows = []
    for n in range(limit):
        rows.append((n, math.factorial(n)))
    return rows

def main():
    rows = factorial_table(11)
    for n, value in rows:
        print(n, value)
    print("choose", choose(20, 5), choose(10, 10), choose(5, 9))
    print("perm", arrangements(20, 5), arrangements(10, 0), arrangements(5, 9))
    print("gcds", math.gcd(14, 21), math.gcd(-14, 21), math.gcd(0, 7))
    print("lcms", math.lcm(14, 21), math.lcm(0, 7), math.lcm(-6, 8))
    for call in ("factorial", "comb", "perm"):
        try:
            if call == "factorial":
                print(math.factorial(-1))
            elif call == "comb":
                print(math.comb(-1, 2))
            else:
                print(math.perm(2, -1))
        except ValueError as exc:
            print(call, "failed:", exc)

main()
