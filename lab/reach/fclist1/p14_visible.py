def fill(out, n, v):
    i = 0
    while i < n:
        out[i] = v + i
        i += 1


def total(xs, n):
    s = 0
    i = 0
    while i < n:
        s += xs[i]
        i += 1
    return s


def main():
    a = [0] * 5
    fill(a, 5, 10)
    print(total(a, 5))
    fill(a, 3, -1)
    print(total(a, 5), a[0], a[4])


main()
