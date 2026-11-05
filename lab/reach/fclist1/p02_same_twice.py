def f(a, b, n):
    i = 0
    while i < n:
        a[i] = a[i] + 1
        b[i] = b[i] * 2
        i += 1


def main():
    x = [1, 2, 3]
    f(x, x, 3)
    print(x)
    y = [5, 6, 7]
    f(x, y, 3)
    print(x, y)


main()
