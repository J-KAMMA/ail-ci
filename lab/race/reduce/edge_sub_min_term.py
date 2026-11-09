MINV = -9223372036854775807 - 1


def main():
    xs = [0, MINV]
    acc = 0
    for i in par_range(0, 2):
        acc -= xs[i]
    print(acc)


main()
