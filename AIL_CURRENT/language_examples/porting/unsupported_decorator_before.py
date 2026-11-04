def twice(function):
    def inner(value: int) -> int:
        return function(function(value))

    return inner


@twice
def bump(value: int) -> int:
    return value + 1


print(bump(3))
