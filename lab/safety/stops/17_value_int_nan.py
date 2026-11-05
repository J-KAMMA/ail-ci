def whole(value: float) -> int:
    return int(value)


print("prefix", whole(2.0))
print("negative", whole(-2.0))
print("next", whole(float("nan")))
