xs: list[int] = [1, 2, 3]


def note(x: int) -> bool:
    if len(xs) < 6:
        xs.append(x * 10)
    return True


picked: list[int] = []
for x in (x for x in xs if note(x)):
    picked.append(x)
    if len(picked) > 8:
        break
print("picked", picked)
print("final", xs)
