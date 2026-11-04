import ail_array as ta


def main():
    big = 4611686018427387904
    top = 9223372036854775807
    m = ta.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], ta.f64)
    for i in (big, -big, top, -top, 2, -3, 1, -2):
        for j in (big, -big, top, -top, 3, -4, 0, -3):
            try:
                print(i, j, m[i, j])
            except IndexError as exc:
                print(i, j, "IndexError", exc)
    for i in (big, -big, top, -top, 2, -3, 1, -2):
        try:
            print(i, m[i])
        except IndexError as exc:
            print(i, "IndexError", exc)
        try:
            m[i, 0] = 1.5
        except IndexError as exc:
            print(i, "IndexError set", exc)
    for lo in (0, 1, -1, big, -big, top, -top):
        for hi in (0, 5, -2, big, -big, top, -top):
            for st in (1, -1, 2, big, -big, top, -top):
                print(lo, hi, st, m[lo:hi:st])
    for r in (0, 1, 3):
        for c in (0, 2):
            z = ta.zeros((r, c), ta.f64)
            print(r, c, z, len(z), z.T.tobytes().hex())
    for r in (-1, -big, -top):
        try:
            print(ta.zeros((r, 2), ta.f64))
        except ValueError as exc:
            print("ValueError", exc)
        try:
            print(ta.zeros((2, r), ta.f64))
        except ValueError as exc:
            print("ValueError", exc)
    try:
        z = ta.zeros((0, big), ta.f64)
        r2, c2 = z.shape
        print(r2, c2, len(z))
    except ValueError as exc:
        print("ValueError", exc)


main()
