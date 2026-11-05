xs: list[int] = [3, 1, 2]


def key(x: int) -> int:
    xs.append(x)
    return x


try:
    ys: list[int] = sorted(xs, key=key)
    print("sorted", ys)
finally:
    print("final", xs)
