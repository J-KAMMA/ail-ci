def bump(xs):
    xs[1] = xs[1] + 10


def main():
    d = {'a': [1, 2], 'b': [3, 4]}
    bump(d['a'])
    print(d)


main()
