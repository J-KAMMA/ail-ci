def pop_inside(xs: list[int]) -> int:
    s = 0
    for i in range(len(xs)):
        s += xs[i]
        if i == 2:
            xs.pop()
    return s


def append_inside(xs: list[int]) -> int:
    s = 0
    for i in range(len(xs)):
        s += xs[i]
        if i < 3:
            xs.append(i)
    return s


def del_inside(xs: list[int]) -> int:
    s = 0
    for i in range(len(xs)):
        s += xs[i]
        if i == 1:
            del xs[0]
    return s


def clear_inside(xs: list[int]) -> int:
    s = 0
    for i in range(len(xs)):
        s += xs[i]
        if i == 3:
            xs.clear()
    return s


def slice_inside(xs: list[int]) -> int:
    s = 0
    for i in range(len(xs)):
        s += xs[i]
        if i == 2:
            xs[1:] = [7]
    return s


def slice_grow(xs: list[int]) -> int:
    s = 0
    for i in range(len(xs)):
        s += xs[i]
        if i == 2:
            xs[1:2] = [7, 8, 9, 10]
    return s


def alias_inside(xs: list[int], ys: list[int]) -> int:
    s = 0
    for i in range(len(xs)):
        s += xs[i]
        if i == 4:
            ys.pop()
            ys.pop()
    return s


def main():
    for k in range(6):
        xs = [1, 2, 3, 4, 5, 6, 7, 8]
        try:
            if k == 0:
                print("pop", pop_inside(xs), xs)
            elif k == 1:
                print("append", append_inside(xs), xs)
            elif k == 2:
                print("del", del_inside(xs), xs)
            elif k == 3:
                print("clear", clear_inside(xs), xs)
            elif k == 4:
                print("slice", slice_inside(xs), xs)
            else:
                print("slice_grow", slice_grow(xs), xs)
        except IndexError as e:
            print(k, "IndexError", e, xs)
    xs = [1, 2, 3, 4, 5, 6, 7, 8]
    try:
        print("alias", alias_inside(xs, xs), xs)
    except IndexError as e:
        print("alias IndexError", e, xs)
    ys = [9, 9, 9]
    print("noalias", alias_inside([1, 2, 3, 4, 5, 6], [0, 0, 0, 0]))


main()
