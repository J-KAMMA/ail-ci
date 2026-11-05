def deco(fn):
    def inner(x):
        return fn(x) * 10
    return inner


@deco
def bump(x):
    return x + 1


print(bump(1))
