def make() -> dict[int, int]:
    return {2: 3}


def f(base: dict[int, int]) -> None:
    d = {True: 1}
    d = base
    for k in d:
        print(k)


f(make())
