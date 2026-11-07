def last(xs, v):
    xs[-1] = v
    xs[-len(xs)] = v + 1


def bad(xs):
    xs[5] = 1


def main():
    a = [1, 2, 3]
    last(a, 7)
    print(a)
    last(a, 9)
    print(a[0], a[1], a[2])
    a2 = [5]
    last(a2, 3)
    print(a2)
    b = [1, 2]
    try:
        bad(b)
    except IndexError:
        print('IndexError', b)


main()
