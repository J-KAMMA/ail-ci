def first(xs):
    xs[0] = 1


def main():
    a = []
    try:
        first(a)
        print('stored', a)
    except IndexError:
        print('IndexError', a)
    first([])


main()
