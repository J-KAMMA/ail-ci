def remainder(a: int, b: int) -> int:
    return a % b


zero = 0
print("prefix", remainder(17, 5))
print("negative", remainder(-17, 5))
print("next", remainder(17, zero))
