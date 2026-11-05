xs: list[int] = [3, 1, 2]


def key(x: int) -> int:
    xs.append(x)
    return x


try:
    xs.sort(key=key)
finally:
    print("final", xs)
