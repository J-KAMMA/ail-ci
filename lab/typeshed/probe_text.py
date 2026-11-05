import math


def main():
    marker = [1]
    marker.append(2.5)         # forces the general path
    n = int("".join(["99999999999999999999"]))
    print(math.gcd(n, n))
    print(len(marker))


main()
