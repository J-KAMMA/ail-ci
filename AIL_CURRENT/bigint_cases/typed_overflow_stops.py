def fact(n):
    r = 1
    for i in range(1, n + 1):
        r *= i
    return r


def main():
    print(fact(20))
    print("before the overflow")
    print(fact(25))
    print("not reached")


main()
