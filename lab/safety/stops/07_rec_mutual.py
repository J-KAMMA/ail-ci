def ping(n: int) -> int:
    return pong(n + 1)


def pong(n: int) -> int:
    return ping(n + 1)


print("prefix", 10)
print("start", ping(0))
print("unreachable", 1)
