BIG = 4611686018427387904


def main():
    xs = [1, BIG, BIG]
    acc = BIG
    for i in range(0, 3):
        acc += xs[i]
    print(acc)


main()
