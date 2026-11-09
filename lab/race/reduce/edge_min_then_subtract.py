MINV = -9223372036854775807 - 1


def main():
    xs = [0, 0, 0, 0, 0, 0, 0, 1]
    acc = MINV
    for i in par_range(0, 8):
        acc -= xs[i]
    print(acc)


main()
