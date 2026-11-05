saved = []


def stash(xs):
    xs[0] = 5
    saved.append(xs)


def main():
    a = [1, 2, 3]
    stash(a)
    a[1] = 8
    print(a, saved)


main()
