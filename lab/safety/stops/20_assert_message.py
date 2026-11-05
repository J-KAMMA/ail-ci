def check(value: int) -> int:
    assert value > 0, "value must be positive"
    return value


print("prefix", check(3))
print("large", check(100))
print("next", check(-1))
