def mark(xs, i):
    xs[i] = -xs[i]


def grow(xs):
    if len(xs) < 6:
        xs.append(len(xs))


def main():
    a = [1, 2, 3, 4]
    i = 0
    for x in a:
        mark(a, len(a) - 1 - i)
        print(x)
        i += 1
    print(a)
    b = [0, 1]
    for y in b:
        grow(b)
        print(y)
    print(b)


main()
