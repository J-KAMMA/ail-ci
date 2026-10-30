import sys


def main():
    data = sys.stdin.read().split()
    xs = [int(w) for w in data]
    tot = 0
    for i in range(len(xs)):
        tot += xs[i] * 3
    print(tot)
    k = 0
    while k < len(xs):
        k += 1
    print(k)
    m = 0
    for i in range(len(xs)):
        j = xs[i] + i
        m = m + j
    print(m)
    print(max(xs) + 1)


main()
