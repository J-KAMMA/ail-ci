def mark(flags, i):
    flags[i] = True


def main():
    f = [False] * 4
    mark(f, 2)
    print(f)
    n = 0
    for x in f:
        if x:
            n += 1
    print(n)


main()
