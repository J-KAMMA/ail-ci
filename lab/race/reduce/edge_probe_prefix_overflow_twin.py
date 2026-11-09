BIG = 4611686018427387904


def main():
    xs = [BIG] * 200
    acc = BIG
    for i in range(0, 200):
        acc += xs[i]
    print(acc)


main()
