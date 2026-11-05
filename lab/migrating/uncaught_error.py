def check(n: int) -> int:
    if n < 0:
        raise ValueError("negative")
    return n

print(check(-1))
