def split(a: int, b: int):
    return divmod(a, b)


zero = 0
print("prefix", split(17, 5))
print("negative", split(-17, 5))
print("next", split(17, zero))
