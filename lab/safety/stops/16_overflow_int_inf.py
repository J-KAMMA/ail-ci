def whole(value: float) -> int:
    return int(value)


print("prefix", whole(3.9))
print("negative", whole(-2.5))
print("next", whole(float("inf")))
