def quotient(a: int, b: int) -> int:
    return a // b


text = "0"
zero = int(text)
print("prefix", quotient(17, 3))
print("negative", quotient(-17, 3))
print("next", quotient(17, zero))
