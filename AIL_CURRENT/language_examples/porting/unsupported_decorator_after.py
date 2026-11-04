def bump(value: int) -> int:
    return value + 1


def bump_twice(value: int) -> int:
    return bump(bump(value))


print(bump_twice(3))
