xs: list[int] = [1, 2, 3]


def note(x: int) -> bool:
    if len(xs) < 6:
        xs.append(x * 10)
    return True


picked: list[int] = [x for x in xs if note(x)]
print("picked", picked)
print("final", xs)
