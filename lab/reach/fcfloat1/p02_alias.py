def fill(out, n):
    i = 0
    while i < n:
        out[i] = i * 0.25
        i += 1


def main():
    a = [0.0, 0.0, 0.0]
    b = a
    fill(a, 3)
    print(repr(b[0]), repr(b[1]), repr(b[2]))
    print(b is a)


main()
